<template>
  <section class="jev-insight" aria-label="Jev 消息分类">
    <header class="jev-insight__header">
      <span class="jev-insight__brand" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="m12 3-1.1 3.2a6.7 6.7 0 0 1-4.2 4.2L3.5 11.5l3.2 1.1a6.7 6.7 0 0 1 4.2 4.2L12 20l1.1-3.2a6.7 6.7 0 0 1 4.2-4.2l3.2-1.1-3.2-1.1a6.7 6.7 0 0 1-4.2-4.2L12 3Z" />
        </svg>
      </span>
      <strong>Jev 洞察</strong>
      <span v-if="entry.status === 'success'" class="jev-insight__model">{{ entry.cacheHit ? '已复用本地缓存' : (entry.result?.generated ? '按这句临时分类' : entry.result?.model) }}</span>
      <span v-else class="jev-insight__model">消息洞察</span>
    </header>

    <div v-if="entry.status === 'loading'" class="jev-insight__loading" role="status">
      <span></span><span></span><span></span>
      <p>正在结合前文分类…</p>
    </div>

    <div v-else-if="entry.status === 'error'" class="jev-insight__error" role="alert">
      <p>{{ entry.error }}</p>
      <button type="button" @click="retryJevInsight(message)">重试</button>
    </div>

    <button
      v-else-if="entry.status !== 'success'"
      type="button"
      class="jev-insight__analyze"
      @click="requestJevInsight(message)"
    >分析此消息</button>

    <template v-else>
      <div class="jev-insight__section">
        <p class="jev-insight__title">可能在说</p>
        <div
          v-for="item in topProbabilities(entry.result?.meaning?.probabilities)"
          :key="item.key"
          class="jev-insight__probability"
        >
          <span><i aria-hidden="true"></i>{{ item.label }}</span>
          <strong>{{ percent(item.probability) }}</strong>
        </div>
      </div>

      <div class="jev-insight__section jev-insight__section--reply">
        <p class="jev-insight__title">回复建议</p>
        <p
          v-for="(item, index) in topProbabilities(entry.result?.reply?.probabilities, 2)"
          :key="item.key"
          class="jev-insight__suggestion"
          :class="{ 'jev-insight__suggestion--alt': index > 0 }"
        >
          <strong>{{ percent(item.probability) }}</strong>
          <span>{{ item.label }}</span>
        </p>
      </div>

      <div class="jev-insight__section jev-insight__section--action">
        <p class="jev-insight__title">沟通目的</p>
        <div
          v-for="item in topProbabilities(entry.result?.intent?.probabilities, 2)"
          :key="item.key"
          class="jev-insight__probability"
        >
          <span><i aria-hidden="true"></i>{{ item.label }}</span>
          <strong>{{ percent(item.probability) }}</strong>
        </div>
      </div>

      <div class="jev-insight__summary">
        <p><span>紧张程度</span>{{ tensionLabel(entry.result?.tension) }}</p>
        <p v-if="entry.result?.context_count || entry.result?.used_profile">
          <span>依据</span>前文 {{ Number(entry.result?.context_count || 0) }} 条<span v-if="entry.result?.used_profile">，含自定义提示词</span>
        </p>
      </div>

      <p v-if="Number(entry.result?.needs_context || 0) >= 0.55" class="jev-insight__context-warning">
        上下文可能不足（{{ percent(entry.result?.needs_context) }}），请勿把分类当作对方真实想法。
      </p>
      <p v-else class="jev-insight__disclaimer">概率分类仅供沟通参考，不代表读心或事实判断。</p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  state: { type: Object, required: true }
})

const entry = computed(() => props.state.jevInsightFor(props.message))
const requestJevInsight = (...args) => props.state.requestJevInsight(...args)
const retryJevInsight = (message) => {
  props.state.requestJevInsight(message, { force: true, manual: true })
}
const percent = value => `${Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100)}%`
const topProbabilities = (values, maxItems = 3) => (Array.isArray(values) ? values : []).slice(0, maxItems)
const tensionLabel = value => {
  const score = Number(value || 0)
  if (score >= 2.5) return `${score.toFixed(1)} / 3 · 高`
  if (score >= 1.5) return `${score.toFixed(1)} / 3 · 中等`
  if (score >= 0.5) return `${score.toFixed(1)} / 3 · 轻微`
  return `${score.toFixed(1)} / 3 · 低`
}
</script>

<style scoped>
.jev-insight { box-sizing:border-box; width:min(300px, calc(100vw - 110px)); margin-top:6px; padding:10px 12px; border:1px solid var(--app-border, #dfe3e0); border-radius:6px; background:var(--app-surface-soft, #f5f6f5); box-shadow:0 1px 2px #00000008; color:var(--app-text-primary, #28302b); font-size:12px; line-height:1.5; }
.jev-insight__header { display:flex; align-items:center; gap:6px; margin-bottom:9px; padding-bottom:7px; border-bottom:1px solid var(--app-border, #dfe3e0); }
.jev-insight__header > strong { font-size:11px; font-weight:600; }
.jev-insight__brand { display:grid; width:18px; height:18px; place-items:center; border-radius:5px; background:color-mix(in srgb, #07c160 10%, var(--app-surface-bg, #fff)); color:#079b57; }
.jev-insight__brand svg { width:11px; height:11px; }
.jev-insight__model { min-width:0; margin-left:auto; color:var(--app-text-muted, #7a817c); font-size:9px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jev-insight__section { display:grid; gap:3px; }
.jev-insight__section--action,.jev-insight__section--reply { margin-top:9px; padding-top:7px; border-top:1px solid var(--app-border, #dfe3e0); }
.jev-insight__title { margin:0 0 2px; color:var(--app-text-muted, #717873); font-size:10px; font-weight:500; }
.jev-insight__suggestion { display:flex; gap:8px; margin:0; align-items:flex-start; }
.jev-insight__suggestion strong { flex:0 0 32px; color:#078b4c; font-size:10px; font-weight:600; line-height:1.6; }
.jev-insight__suggestion span { min-width:0; }
.jev-insight__suggestion--alt { color:var(--app-text-muted, #717873); }
.jev-insight__suggestion--alt strong { color:var(--app-text-muted, #717873); }
.jev-insight__probability { display:grid; grid-template-columns:minmax(0,1fr) 34px; gap:8px; align-items:start; }
.jev-insight__probability span { display:flex; min-width:0; align-items:baseline; gap:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jev-insight__probability span i { flex:none; width:3px; height:3px; border-radius:50%; background:var(--app-text-muted, #858b87); }
.jev-insight__probability strong { text-align:right; color:var(--app-text-secondary, #626a65); font-size:10px; font-weight:500; }
.jev-insight__summary { display:grid; gap:3px; margin-top:9px; padding-top:7px; border-top:1px solid var(--app-border, #dfe3e0); }
.jev-insight__summary p { margin:0; }
.jev-insight__summary span { display:inline-block; min-width:54px; margin-right:6px; color:var(--app-text-muted, #717873); font-size:10px; }
.jev-insight__disclaimer,.jev-insight__context-warning { margin:7px 0 0; font-size:9px; line-height:1.5; color:var(--app-text-muted, #777); }
.jev-insight__context-warning { color:#946200; }
.jev-insight__loading { display:flex; flex-wrap:wrap; align-items:center; gap:4px; color:var(--app-text-muted, #777); }
.jev-insight__loading span { width:4px; height:4px; border-radius:50%; background:#07a85a; animation:jev-pulse 1s infinite ease-in-out; }
.jev-insight__loading span:nth-child(2) { animation-delay:.15s; }.jev-insight__loading span:nth-child(3) { animation-delay:.3s; }
.jev-insight__loading p { width:100%; margin:3px 0 0; }
.jev-insight__error p { margin:0 0 6px; color:#b42318; }.jev-insight__error button,.jev-insight__analyze { border:0; padding:0; color:#078c4a; background:transparent; cursor:pointer; font:inherit; font-weight:500; }
:global(html[data-theme='dark']) .jev-insight { box-shadow:none; }
@keyframes jev-pulse { 0%,100%{opacity:.25;transform:translateY(0)} 50%{opacity:1;transform:translateY(-2px)} }
@media (prefers-reduced-motion: reduce) { .jev-insight__loading span { animation:none; } }
</style>
