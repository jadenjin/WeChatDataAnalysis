import { computed, onUnmounted, ref, watch } from 'vue'

const AUTO_ANALYZE_LIMIT = 10
const MAX_CONCURRENT = 2
const STORAGE_KEY = 'jev-conversation-settings:v1'
const CACHE_STORAGE_KEY = 'jev-message-insights-cache:v1'
const CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000
const CACHE_MAX_ENTRIES = 300
export const JEV_CONTEXT_PRESETS = [10, 20, 50, 100]
export const JEV_CONTEXT_MAX = 100
export const JEV_PROMPT_MAX = 2000
const CONTEXT_TEXT_MAX = 500
const MESSAGE_TEXT_MAX = 2000

const messageKey = (message) => String(message?.id ?? message?.serverIdStr ?? '').trim()

const TYPE_FALLBACK = {
  image: '[图片]',
  video: '[视频]',
  voice: '[语音]',
  emoji: '[表情]',
  file: '[文件]',
  link: '[链接]',
  transfer: '[转账]',
  redPacket: '[红包]',
  redpacket: '[红包]',
  location: '[位置]'
}

export const clampJevContextLimit = (value) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return 20
  return Math.max(1, Math.min(JEV_CONTEXT_MAX, Math.round(number)))
}

export const normalizeJevSettings = (raw = {}) => ({
  enabled: !!raw.enabled,
  contextLimit: clampJevContextLimit(raw.contextLimit ?? 20),
  prompt: String(raw.prompt || '').slice(0, JEV_PROMPT_MAX)
})

export const isJevInsightEligible = (message) => {
  return !!(
    message
    && !message.isSent
    && message.renderType === 'text'
    && String(message.content || '').trim()
    && messageKey(message)
  )
}

export const jevContextText = (message) => {
  const type = String(message?.renderType || '').trim()
  if (type === 'system') return ''
  const content = String(message?.content || '').replace(/\s+/g, ' ').trim()
  if (type === 'text') return content.slice(0, CONTEXT_TEXT_MAX)
  if (content) return content.slice(0, 200)
  return TYPE_FALLBACK[type] || ''
}

export const buildJevContext = (messages, message, requestedLimit) => {
  const list = Array.isArray(messages) ? messages : []
  const index = list.findIndex(item => messageKey(item) && messageKey(item) === messageKey(message))
  if (index <= 0) return []
  const cap = clampJevContextLimit(requestedLimit)
  return list
    .slice(Math.max(0, index - cap), index)
    .map((item) => {
      const text = jevContextText(item)
      if (!text) return null
      return {
        role: item.isSent ? 'self' : 'other',
        text
      }
    })
    .filter(Boolean)
    .slice(-cap)
}

const memoryStore = {}
const memoryCacheStore = {}

const browserStorage = () => {
  try {
    const storage = globalThis.window?.localStorage
    if (storage && typeof storage.getItem === 'function' && typeof storage.setItem === 'function') return storage
  } catch {
    return null
  }
  return null
}

const rememberStore = (store) => {
  for (const key of Object.keys(memoryStore)) delete memoryStore[key]
  Object.assign(memoryStore, store)
}

const rememberCacheStore = (store) => {
  for (const key of Object.keys(memoryCacheStore)) delete memoryCacheStore[key]
  Object.assign(memoryCacheStore, store)
}

export const resetJevSettingsStore = () => {
  rememberStore({})
  rememberCacheStore({})
  try {
    browserStorage()?.removeItem(STORAGE_KEY)
    browserStorage()?.removeItem(CACHE_STORAGE_KEY)
  } catch {
    /* 浏览器禁止本地存储时，内存副本已经清空。 */
  }
}

const readCacheStore = () => {
  const storage = browserStorage()
  if (!storage) return { ...memoryCacheStore }
  try {
    const parsed = JSON.parse(storage.getItem(CACHE_STORAGE_KEY) || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { ...memoryCacheStore }
    const now = Date.now()
    const fresh = Object.fromEntries(
      Object.entries(parsed).filter(([, item]) => (
        item && typeof item === 'object' && now - Number(item.savedAt || 0) <= CACHE_TTL_MS
      ))
    )
    rememberCacheStore(fresh)
    return fresh
  } catch {
    return { ...memoryCacheStore }
  }
}

const writeCacheStore = (store) => {
  const entries = Object.entries(store)
    .filter(([, item]) => item && typeof item === 'object')
    .sort((left, right) => Number(right[1].savedAt || 0) - Number(left[1].savedAt || 0))
    .slice(0, CACHE_MAX_ENTRIES)
  const trimmed = Object.fromEntries(entries)
  rememberCacheStore(trimmed)
  const storage = browserStorage()
  if (!storage) return
  try {
    storage.setItem(CACHE_STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    /* 缓存写满时不影响正常分析，当前运行仍保留内存副本。 */
  }
}

const requestFingerprint = (payload) => {
  const text = JSON.stringify(payload)
  let first = 0x811c9dc5
  let second = 0x9e3779b9
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index)
    first = Math.imul(first ^ code, 0x01000193)
    second = Math.imul(second ^ code, 0x85ebca6b)
  }
  return `${(first >>> 0).toString(16).padStart(8, '0')}${(second >>> 0).toString(16).padStart(8, '0')}:${text.length}`
}

const readStore = () => {
  const storage = browserStorage()
  if (!storage) return { ...memoryStore }
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { ...memoryStore }
    rememberStore(parsed)
    return parsed
  } catch {
    return { ...memoryStore }
  }
}

const writeStore = (store) => {
  rememberStore(store)
  const storage = browserStorage()
  if (!storage) return
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(store))
  } catch {
    /* 隐私模式或存储配额不足时，至少在本次运行中保留各会话配置。 */
  }
}

export const useJevMessageInsights = ({ selectedAccount, selectedContact, renderMessages }) => {
  const { request } = useAiApi()
  const jevInsightsEnabled = ref(false)
  const jevContextLimit = ref(20)
  const jevPrompt = ref('')
  const jevSettingsOpen = ref(false)
  const jevDraftEnabled = ref(false)
  const jevDraftContextLimit = ref(20)
  const jevDraftPrompt = ref('')
  const jevStatus = ref(null)
  const jevStatusLoading = ref(false)
  const jevInsightEntries = ref({})
  const manualInsightKeys = ref({})
  const queue = []
  const queued = new Set()
  let active = 0
  let generation = 0
  let disposed = false
  let statusPromise = null

  const contactStorageKey = () => {
    const account = String(selectedAccount?.value || '').trim()
    const username = String(selectedContact?.value?.username || '').trim()
    return username ? `${account}::${username}` : ''
  }

  const insightCacheKey = (message) => `${contactStorageKey()}::${messageKey(message)}`

  const requestPayload = (message, contextLimit = jevContextLimit.value, prompt = jevPrompt.value) => ({
    message: String(message?.content || '').trim().slice(0, MESSAGE_TEXT_MAX),
    context: buildJevContext(renderMessages.value, message, contextLimit),
    prompt: String(prompt || '').slice(0, JEV_PROMPT_MAX)
  })

  const cachedInsight = (message, payload) => {
    const item = readCacheStore()[insightCacheKey(message)]
    if (!item || item.fingerprint !== requestFingerprint(payload) || !item.result || typeof item.result !== 'object') {
      return null
    }
    return item.result
  }

  const persistInsight = (message, payload, result) => {
    if (!result || typeof result !== 'object') return
    const store = readCacheStore()
    store[insightCacheKey(message)] = {
      fingerprint: requestFingerprint(payload),
      result,
      savedAt: Date.now()
    }
    writeCacheStore(store)
  }

  const restoreCachedInsight = (message, payload = requestPayload(message)) => {
    const result = cachedInsight(message, payload)
    if (!result) return false
    setEntry(messageKey(message), {
      status: 'success',
      result,
      error: '',
      cacheHit: true,
      fingerprint: requestFingerprint(payload)
    })
    return true
  }

  const persistCurrent = () => {
    const key = contactStorageKey()
    if (!key) return
    const store = readStore()
    store[key] = {
      enabled: jevInsightsEnabled.value,
      contextLimit: jevContextLimit.value,
      prompt: jevPrompt.value
    }
    writeStore(store)
  }

  const loadCurrentSettings = () => {
    const key = contactStorageKey()
    const settings = normalizeJevSettings(key ? readStore()[key] : {})
    jevInsightsEnabled.value = settings.enabled
    jevContextLimit.value = settings.contextLimit
    jevPrompt.value = settings.prompt
    jevDraftEnabled.value = settings.enabled
    jevDraftContextLimit.value = settings.contextLimit
    jevDraftPrompt.value = settings.prompt
  }

  const setEntry = (key, patch) => {
    jevInsightEntries.value = {
      ...jevInsightEntries.value,
      [key]: { ...(jevInsightEntries.value[key] || {}), ...patch }
    }
  }

  const runNext = () => {
    if (disposed) return
    while (active < MAX_CONCURRENT && queue.length) {
      const job = queue.shift()
      queued.delete(job.key)
      if (job.generation !== generation) continue
      const current = jevInsightEntries.value[job.key]
      if (!job.force && current?.status === 'success' && current?.fingerprint === job.fingerprint) continue
      if (!job.manual && !jevInsightsEnabled.value) continue
      active += 1
      setEntry(job.key, { status: 'loading', error: '', fingerprint: job.fingerprint })
      request('/jev/message-insights', {
        method: 'POST',
        body: job.payload
      }).then((result) => {
        if (job.generation === generation) {
          persistInsight(job.message, job.payload, result)
          setEntry(job.key, {
            status: 'success',
            result,
            error: '',
            cacheHit: false,
            fingerprint: job.fingerprint
          })
        }
      }).catch((error) => {
        if (job.generation === generation) {
          setEntry(job.key, { status: 'error', error: String(error?.message || 'Jev 分类失败，请重试') })
        }
      }).finally(() => {
        active = Math.max(0, active - 1)
        runNext()
      })
    }
  }

  const requestJevInsight = (message, { force = false, manual = false } = {}) => {
    if ((!manual && !jevInsightsEnabled.value) || !isJevInsightEligible(message)) return
    const key = messageKey(message)
    const payload = requestPayload(message)
    const fingerprint = requestFingerprint(payload)
    const current = jevInsightEntries.value[key]
    if (!force && (
      (current?.fingerprint === fingerprint && ['loading', 'success'].includes(current?.status))
      || queued.has(key)
    )) return
    if (!force && restoreCachedInsight(message, payload)) return
    if (force) {
      const queuedIndex = queue.findIndex(item => item.key === key)
      if (queuedIndex >= 0) queue.splice(queuedIndex, 1)
      queued.delete(key)
    }
    queue.push({
      key,
      message,
      generation,
      manual,
      force,
      payload,
      fingerprint
    })
    queued.add(key)
    runNext()
  }

  const scheduleRecent = () => {
    if (!jevInsightsEnabled.value || jevStatus.value?.configured !== true) return
    const list = (Array.isArray(renderMessages.value) ? renderMessages.value : [])
      .filter(isJevInsightEligible)
      .slice(-AUTO_ANALYZE_LIMIT)
    for (const message of list) requestJevInsight(message)
  }

  const refreshJevStatus = () => {
    if (jevStatus.value?.configured === true) return Promise.resolve(jevStatus.value)
    if (statusPromise) return statusPromise
    jevStatusLoading.value = true
    statusPromise = request('/jev/status').then((result) => {
      jevStatus.value = result
      return result
    }).catch((error) => {
      jevStatus.value = { configured: false, error: String(error?.message || '无法检查 Jev 配置') }
      return jevStatus.value
    }).finally(() => {
      jevStatusLoading.value = false
      statusPromise = null
    })
    return statusPromise
  }

  const resetAnalysis = () => {
    generation += 1
    queue.splice(0)
    queued.clear()
    jevInsightEntries.value = {}
    manualInsightKeys.value = {}
  }

  const analyzeJevMessage = async (message) => {
    if (!isJevInsightEligible(message)) return
    const key = messageKey(message)
    manualInsightKeys.value = { ...manualInsightKeys.value, [key]: true }
    if (restoreCachedInsight(message)) return
    const status = jevStatus.value?.configured === true ? jevStatus.value : await refreshJevStatus()
    if (!status?.configured) {
      setEntry(key, {
        status: 'error',
        error: status?.error || 'Jev 尚未配置：请前往设置 → AI 服务填写 AI 分类模型 API 密钥。'
      })
      return
    }
    requestJevInsight(message, { manual: true })
  }

  const jevInsightVisible = (message) => {
    if (!isJevInsightEligible(message)) return false
    if (jevInsightsEnabled.value) return true
    return !!manualInsightKeys.value[messageKey(message)]
  }

  const ensureAnalysis = async () => {
    if (!jevInsightsEnabled.value) return
    const status = await refreshJevStatus()
    if (status?.configured) scheduleRecent()
  }

  const toggleJevSettings = () => {
    if (!jevSettingsOpen.value) {
      jevDraftEnabled.value = jevInsightsEnabled.value
      jevDraftContextLimit.value = jevContextLimit.value
      jevDraftPrompt.value = jevPrompt.value
    }
    jevSettingsOpen.value = !jevSettingsOpen.value
  }

  const setJevDraftContextLimit = (value) => {
    jevDraftContextLimit.value = clampJevContextLimit(value)
  }

  const applyJevSettings = async (overrides = {}) => {
    const next = normalizeJevSettings({
      enabled: jevDraftEnabled.value,
      contextLimit: jevDraftContextLimit.value,
      prompt: jevDraftPrompt.value,
      ...overrides
    })
    jevInsightsEnabled.value = next.enabled
    jevContextLimit.value = next.contextLimit
    jevPrompt.value = next.prompt
    jevDraftEnabled.value = next.enabled
    jevDraftContextLimit.value = next.contextLimit
    jevDraftPrompt.value = next.prompt
    persistCurrent()
    jevSettingsOpen.value = false
    resetAnalysis()
    if (next.enabled) await ensureAnalysis()
    return next
  }

  const disableJevInsights = () => applyJevSettings({ enabled: false })

  const jevInsightNotice = computed(() => {
    if (!jevInsightsEnabled.value) return ''
    if (jevStatusLoading.value && !jevStatus.value) return '正在检查 Jev 配置…'
    if (jevStatus.value?.error) return jevStatus.value.error
    if (jevStatus.value && !jevStatus.value.configured) {
      return 'Jev 尚未配置：请前往设置 → AI 服务填写 AI 分类模型 API 密钥。'
    }
    return ''
  })

  const jevInsightFor = (message) => jevInsightEntries.value[messageKey(message)] || { status: 'idle' }

  watch(
    () => (Array.isArray(renderMessages.value) ? renderMessages.value : [])
      .filter(isJevInsightEligible)
      .map(message => `${messageKey(message)}:${String(message.content || '').length}`)
      .join('|'),
    scheduleRecent
  )

  watch(
    () => `${String(selectedAccount?.value || '').trim()}::${String(selectedContact?.value?.username || '').trim()}`,
    async () => {
      jevSettingsOpen.value = false
      resetAnalysis()
      loadCurrentSettings()
      await ensureAnalysis()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    disposed = true
    generation += 1
    queue.splice(0)
    queued.clear()
  })

  return {
    jevInsightsEnabled,
    jevContextLimit,
    jevPrompt,
    jevSettingsOpen,
    jevDraftEnabled,
    jevDraftContextLimit,
    jevDraftPrompt,
    jevContextPresets: JEV_CONTEXT_PRESETS,
    jevStatus,
    jevStatusLoading,
    jevInsightNotice,
    toggleJevSettings,
    setJevDraftContextLimit,
    applyJevSettings,
    disableJevInsights,
    isJevInsightEligible,
    jevInsightVisible,
    jevInsightFor,
    requestJevInsight,
    analyzeJevMessage
  }
}
