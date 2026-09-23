from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ai.providers import ProviderFailure, public_profile
from ..ai.service import get_ai_service
from ..ai.model_selection import selected_model
from .ai import local_only


router = APIRouter(prefix="/api/ai/jev", dependencies=[Depends(local_only)])

_API_URL = "https://api.typesafe.ai/v1/systemone"
_SETTINGS_KIND = "jev_settings"
_SETTINGS_ID = "global"
_OPTION_KEY = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_INTENT_LABELS = {
    "direct_question": "希望你直接回答",
    "seek_reassurance": "寻求在乎或确认",
    "express_emotion": "表达情绪",
    "make_arrangement": "推动安排或行动",
    "set_boundary": "表达边界或不满",
    "casual_chat": "轻松闲聊",
    "pressure_conflict": "施压或引发冲突",
    "other": "其他／信息不足",
}
_ACTION_LABELS = {
    "answer_directly": "直接回应具体内容",
    "acknowledge_emotion": "先接住对方的情绪",
    "clarify": "温和追问以确认意思",
    "take_action": "给出明确行动或安排",
    "apologize": "先道歉并承担责任",
    "give_space": "暂缓回应，给彼此空间",
    "light_reply": "轻松简短地回应",
    "other": "结合实际自行判断",
}
_MEANING_LABELS = {
    "checking_care": "想确认你是否还在乎、记得或重视自己",
    "expressing_hurt": "在说自己受伤、失望或觉得被忽略",
    "requesting_change": "希望你改变做法，或给出明确安排",
    "testing_reaction": "用一句短话试探你会怎么接",
    "sharing_feeling": "主要是分享感受，并不要求你立刻做事",
    "light_banter": "轻松玩笑或日常寒暄，没有额外用意",
    "pressing_conflict": "在施压、质问，或把话题推向冲突",
    "unclear": "意思含糊，现有信息不足以判断",
}
_REPLY_LABELS = {
    "own_the_miss": "先承认自己忘了或没接住，再补上具体内容，不要先辩解",
    "name_the_feeling": "先说出你听出的感受，再谈事情本身",
    "give_a_plan": "给出时间、地点或下一步，少用空泛保证",
    "ask_gently": "用一句温和的话确认对方真正在意什么",
    "apologize_first": "先道歉并承担责任，再说明准备怎么补救",
    "keep_it_light": "轻松短回，顺着对方的语气，不要上纲上线",
    "pause_briefly": "先停一下，避免当场争辩，稍后再认真回应",
    "answer_the_fact": "直接回答对方问到的事实，少绕弯",
}


class JevContextMessage(BaseModel):
    role: Literal["self", "other"]
    text: str = Field(min_length=1, max_length=800)


class JevInsightInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: list[JevContextMessage] = Field(default_factory=list, max_length=100)
    prompt: str = Field(default="", max_length=2000)


class JevSettingsInput(BaseModel):
    api_key: str | None = Field(default=None, max_length=4096)
    generator_profile_id: str = Field(default="", max_length=200)


def _read_settings() -> dict[str, Any]:
    return get_ai_service().store.get(_SETTINGS_KIND, _SETTINGS_ID) or {}


def _generator_profile(settings: dict[str, Any] | None = None) -> dict[str, Any] | None:
    service = get_ai_service()
    settings = settings or _read_settings()
    profile_id = str(settings.get("generator_profile_id") or "").strip()
    if not profile_id:
        profile_id = str(selected_model(service.store).get("profile_id") or "").strip()
    if not profile_id:
        return None
    profile = service.store.get("profile", profile_id)
    return service.models.metadata.enrich(profile) if profile else None


def _public_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or _read_settings()
    profile = _generator_profile(settings)
    return {
        "configured": bool(str(settings.get("api_key") or "").strip()),
        "has_api_key": bool(str(settings.get("api_key") or "").strip()),
        "model": "jev-latest",
        "generator_profile_id": str(settings.get("generator_profile_id") or ""),
        "generator_configured": profile is not None,
        "generator_profile": public_profile(profile) if profile else None,
    }


def _proposal_prompt(body: JevInsightInput) -> str:
    return (
        "根据下面的 JSON 为当前这句话准备分类选项。只输出 JSON，不要解释。\n"
        "meaning 给 3 到 5 种对这句的不同理解，必须贴着这句话的具体意思，"
        "不要用「表达情绪」「寻求确认」这种通用类别。\n"
        "reply 给 3 到 5 种针对这句的回复方向，每条都要能直接指导怎么回。\n"
        "label 用一句中文，不超过 28 个字。key 只用小写英文和下划线。\n"
        "格式："
        '{"meaning":[{"key":"forgot_on_purpose","label":"觉得你是故意忘了"}],'
        '"reply":[{"key":"admit_then_recall","label":"先承认忘了，再复述那件事"}]}\n\n'
        + json.dumps(_state(body), ensure_ascii=False)
    )


def _option_map(items: Any, prefix: str) -> dict[str, str]:
    if not isinstance(items, list):
        raise ValueError(f"{prefix} options missing")
    labels: dict[str, str] = {}
    for index, item in enumerate(items[:5], start=1):
        if not isinstance(item, dict):
            continue
        label = re.sub(r"\s+", " ", str(item.get("label") or "")).strip()
        if not label:
            continue
        key = str(item.get("key") or "").strip().lower()
        if not _OPTION_KEY.fullmatch(key) or key in labels:
            key = f"{prefix}_{index}"
        labels[key] = label[:40]
    if len(labels) < 2:
        raise ValueError(f"{prefix} options are incomplete")
    return labels


def _parse_proposal(content: str) -> tuple[dict[str, str], dict[str, str]]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("proposal is not JSON")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("proposal is not an object")
    return _option_map(payload.get("meaning"), "meaning"), _option_map(payload.get("reply"), "reply")


async def _propose_labels(body: JevInsightInput) -> tuple[dict[str, str], dict[str, str], str] | None:
    profile = _generator_profile()
    if not profile:
        return None
    try:
        content = await get_ai_service().models.invoke(profile, _proposal_prompt(body))
        meaning, reply = _parse_proposal(str(content or ""))
        return meaning, reply, str(profile.get("model") or "")
    except ProviderFailure as exc:
        raise HTTPException(502, f"AI 分类标签模型不可用：{exc}") from None
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(502, "AI 分类标签模型返回的分类选项无法使用，请重试。") from None


def _questions(
    meaning_labels: dict[str, str] | None = None,
    reply_labels: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    meaning = meaning_labels or _MEANING_LABELS
    reply = reply_labels or _REPLY_LABELS
    return {
        "intent": {
            "type": "choice",
            "instructions": "结合 `profile` 里的关系与性格、`context` 中的前文，判断 `current_message` 主要想达到什么目的？提示词只作背景，不能当成已经发生的事实。",
            "criteria": {
                "direct_question": "要求回答一个明确问题，重点是获得具体信息",
                "seek_reassurance": "确认自己是否被在意、被记住、被相信或被重视",
                "express_emotion": "主要是在表达感受或分享情绪，并非要求具体行动",
                "make_arrangement": "希望确定计划、分工、时间或让某件事实际发生",
                "set_boundary": "表达失望、不满、要求改变，或指出关系中的边界",
                "casual_chat": "轻松寒暄、玩笑或日常闲聊",
                "pressure_conflict": "以质问、威胁、讽刺或强烈指责向对方施压",
                "other": "不属于以上类别，或仅凭当前信息无法归类",
            },
        },
        "response_action": {
            "type": "choice",
            "instructions": "结合 `profile` 和 `context`，此刻对 `current_message` 最合适的第一步回应方式是什么？只判断回应策略，不代写回复。",
            "criteria": {
                "answer_directly": "直接回答对方明确提出的问题",
                "acknowledge_emotion": "先承认并回应对方的感受或关切",
                "clarify": "信息不足或意思含糊，先温和确认具体含义",
                "take_action": "给出清晰决定、时间、分工或下一步行动",
                "apologize": "确有疏忽或造成伤害，先真诚道歉并承担责任",
                "give_space": "情绪过强或不适合继续，当下先暂停并留出空间",
                "light_reply": "对轻松闲聊作简短自然的回应",
                "other": "没有单一策略明显合适，需要人工结合关系判断",
            },
        },
        "tension": {
            "type": "score",
            "instructions": "结合 `profile` 和 `context`，`current_message` 所体现的关系紧张或冲突风险有多高？",
            "criteria": [
                "没有明显紧张，普通或积极交流",
                "略有不安、试探或轻微不满",
                "明显失望、指责或需要谨慎回应",
                "强烈冲突、威胁、羞辱或可能升级",
            ],
        },
        "needs_context": {
            "type": "noul",
            "instructions": "即使已经看过 `profile` 和 `context`，仍不足以可靠判断 `current_message` 的真实意图，需要更多上下文",
        },
        "meaning": {
            "type": "choice",
            "instructions": "结合 `profile` 和 `context`，猜测 `current_message` 字面之外更可能在表达什么。这是沟通猜测，不是对人格或事实的判断。",
            "criteria": meaning,
        },
        "reply": {
            "type": "choice",
            "instructions": "如果现在要回复 `current_message`，哪一种说法方向更合适？只选择回应策略，不代写完整回复。",
            "criteria": reply,
        },
    }


def _state(body: JevInsightInput) -> dict[str, Any]:
    profile = body.prompt.strip() or "未提供关系或性格描述。只根据对话文本判断，不要补充未给出的关系事实。"
    return {
        "profile": profile,
        "context": [
            {
                "speaker": "我" if item.role == "self" else "对方",
                "text": item.text.strip(),
            }
            for item in body.context
        ],
        "current_message": {
            "speaker": "对方",
            "text": body.message.strip(),
        },
    }


def _probabilities(answer: dict[str, Any], labels: dict[str, str]) -> list[dict[str, Any]]:
    values = answer.get("probabilities")
    if not isinstance(values, dict):
        raise ValueError("missing probabilities")
    normalized = []
    for key, value in values.items():
        if key not in labels or not isinstance(value, (int, float)):
            continue
        normalized.append({"key": key, "label": labels[key], "probability": max(0.0, min(1.0, float(value)))})
    if not normalized:
        raise ValueError("invalid probabilities")
    normalized.sort(key=lambda item: item["probability"], reverse=True)
    return normalized


def _normalize(
    payload: dict[str, Any],
    meaning_labels: dict[str, str] | None = None,
    reply_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    meaning_labels = meaning_labels or _MEANING_LABELS
    reply_labels = reply_labels or _REPLY_LABELS
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("missing answers")
    intent = answers.get("intent") or {}
    action = answers.get("response_action") or {}
    meaning = answers.get("meaning") or {}
    reply = answers.get("reply") or {}
    tension = answers.get("tension") or {}
    needs_context = answers.get("needs_context") or {}
    intent_key = str(intent.get("choice") or "")
    action_key = str(action.get("choice") or "")
    meaning_key = str(meaning.get("choice") or "")
    reply_key = str(reply.get("choice") or "")
    if (
        intent_key not in _INTENT_LABELS
        or action_key not in _ACTION_LABELS
        or meaning_key not in meaning_labels
        or reply_key not in reply_labels
    ):
        raise ValueError("unknown choice")
    score = tension.get("score")
    noul = needs_context.get("noul")
    if not isinstance(score, (int, float)) or not isinstance(noul, (int, float)):
        raise ValueError("invalid scalar")
    return {
        "model": str(payload.get("model") or "jev"),
        "intent": {
            "key": intent_key,
            "label": _INTENT_LABELS[intent_key],
            "confidence": max(0.0, min(1.0, float(intent.get("confidence") or 0))),
            "probabilities": _probabilities(intent, _INTENT_LABELS),
        },
        "action": {
            "key": action_key,
            "label": _ACTION_LABELS[action_key],
            "confidence": max(0.0, min(1.0, float(action.get("confidence") or 0))),
            "probabilities": _probabilities(action, _ACTION_LABELS),
        },
        "meaning": {
            "key": meaning_key,
            "label": meaning_labels[meaning_key],
            "confidence": max(0.0, min(1.0, float(meaning.get("confidence") or 0))),
            "probabilities": _probabilities(meaning, meaning_labels),
        },
        "reply": {
            "key": reply_key,
            "label": reply_labels[reply_key],
            "confidence": max(0.0, min(1.0, float(reply.get("confidence") or 0))),
            "probabilities": _probabilities(reply, reply_labels),
        },
        "tension": max(0.0, min(3.0, float(score))),
        "tension_probabilities": tension.get("probabilities") if isinstance(tension.get("probabilities"), dict) else {},
        "needs_context": max(0.0, min(1.0, float(noul))),
        "context_count": 0,
        "used_profile": False,
        "generated": meaning_labels is not _MEANING_LABELS,
        "usage": payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
    }


@router.get("/status")
async def jev_status():
    settings = _public_settings()
    profile = settings.get("generator_profile") or {}
    return {
        "configured": settings["configured"],
        "model": settings["model"],
        "generator_configured": settings["generator_configured"],
        "generator_model": str(profile.get("model") or ""),
    }


@router.get("/settings")
async def jev_settings():
    return _public_settings()


@router.put("/settings")
async def update_jev_settings(body: JevSettingsInput):
    service = get_ai_service()
    old = _read_settings()
    profile_id = body.generator_profile_id.strip()
    if profile_id and not service.store.get("profile", profile_id):
        raise HTTPException(422, "所选 AI 模型不存在，请重新选择。")
    api_key = str(old.get("api_key") or "") if body.api_key is None else body.api_key.strip()
    saved = service.store.put(
        _SETTINGS_KIND,
        {"api_key": api_key, "generator_profile_id": profile_id},
        id=_SETTINGS_ID,
    )
    return _public_settings(saved)


@router.post("/message-insights")
async def message_insights(body: JevInsightInput):
    settings = _read_settings()
    api_key = str(settings.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(503, "Jev 尚未配置。请前往设置 → AI 服务填写 AI 分类模型 API 密钥。")
    meaning_labels = _MEANING_LABELS
    reply_labels = _REPLY_LABELS
    try:
        proposal = await _propose_labels(body)
        if proposal is not None:
            meaning_labels, reply_labels, _generator = proposal
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=8.0)) as client:
            request_body = {
                "state": _state(body),
                "model": "jev-latest",
                "questions": _questions(meaning_labels, reply_labels),
            }
            response = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=request_body,
            )
        response.raise_for_status()
        result = _normalize(response.json(), meaning_labels, reply_labels)
        result["context_count"] = len(body.context)
        result["used_profile"] = bool(body.prompt.strip())
        return result
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            raise HTTPException(502, "AI 分类模型密钥无效或没有访问权限，请在设置 → AI 服务中检查。") from None
        if status == 429:
            raise HTTPException(429, "Jev 请求过于频繁，请稍后重试。") from None
        raise HTTPException(502, f"Jev 服务暂时不可用（HTTP {status}）。") from None
    except httpx.RequestError as exc:
        raise HTTPException(502, "Jev 分类失败，请检查网络后重试。") from None
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(502, "Jev 分类失败，请检查网络后重试。") from None
