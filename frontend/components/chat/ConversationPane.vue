<template>
  <div class="conversation-pane flex-1 flex flex-col min-h-0 min-w-0">
    <div v-if="selectedContact" class="flex-1 flex flex-col min-h-0 min-w-0 relative">
      <div class="chat-header" :class="{ 'chat-header-ai': aiSidebarOpen }">
        <div class="flex min-w-0 items-center gap-3">
          <h2 class="chat-header-title flex min-w-0 items-center gap-1.5 text-base font-medium">
            <span class="min-w-0 truncate" :class="{ 'privacy-blur': privacyMode }">{{ selectedContact.name }}</span>
            <span
              v-if="selectedContact.enterpriseName"
              class="min-w-0 max-w-[16rem] truncate text-[14px] text-[#ff8000]"
              :class="{ 'privacy-blur': privacyMode }"
            >@{{ selectedContact.enterpriseName }}</span>
            <img
              v-if="selectedContact.isEnterpriseGroup"
              src="/assets/images/wechat/wecom.png"
              alt="企业微信群"
              title="企业微信群"
              class="h-4 w-4 shrink-0"
            >
          </h2>
          <button
            v-if="groupAnnouncement"
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-[#07C160] hover:bg-[#07C160]/10"
            aria-haspopup="dialog"
            title="查看群公告"
            @click="openGroupAnnouncement"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M4 13V7l12-3v12L4 13Z" />
              <path d="M8 13v6h3l1-5M19 8v4" />
            </svg>
            <span>群公告</span>
          </button>
        </div>
        <div class="ml-auto flex shrink-0 items-center gap-2">
          <button type="button" class="header-btn-icon" :class="{ 'header-btn-icon-active': aiSidebarOpen }" aria-label="AI 助手" title="AI 助手" :aria-pressed="aiSidebarOpen" @click="toggleAiSidebar">AI</button>
          <button
            type="button"
            class="header-btn-icon header-btn-jev"
            :class="{ 'header-btn-icon-active': jevInsightsEnabled }"
            :aria-pressed="jevInsightsEnabled"
            :aria-expanded="jevSettingsOpen"
            aria-controls="jev-insight-settings"
            aria-label="Jev 消息洞察"
            title="为本会话单独配置 Jev 分析"
            @click="toggleJevSettings"
          >
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="m12 3-1.1 3.2a6.7 6.7 0 0 1-4.2 4.2L3.5 11.5l3.2 1.1a6.7 6.7 0 0 1 4.2 4.2L12 20l1.1-3.2a6.7 6.7 0 0 1 4.2-4.2l3.2-1.1-3.2-1.1a6.7 6.7 0 0 1-4.2-4.2L12 3Z" />
              <path d="m19 3-.35 1.05a2.2 2.2 0 0 1-1.4 1.4L16.2 5.8l1.05.35a2.2 2.2 0 0 1 1.4 1.4L19 8.6l.35-1.05a2.2 2.2 0 0 1 1.4-1.4l1.05-.35-1.05-.35a2.2 2.2 0 0 1-1.4-1.4L19 3Z" />
            </svg>
            <span v-if="jevInsightsEnabled" class="header-btn-jev__dot" aria-hidden="true"></span>
          </button>
          <button
            type="button"
            class="header-btn-icon"
            title="添加消息"
            aria-label="添加消息"
            @click="openFeatureUnavailableDialog"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <button
            type="button"
            class="header-btn-icon"
            :disabled="isLoadingMessages || isJumpingToFirst"
            :aria-busy="isJumpingToFirst"
            aria-label="从第一条消息开始阅读"
            title="从第一条消息开始阅读"
            @click="jumpToConversationFirst"
          >
            <svg class="w-4 h-4" :class="{ 'animate-pulse': isJumpingToFirst }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" aria-hidden="true">
              <path d="M5 4h14" />
              <path d="M12 20V7" />
              <path d="m7.5 11.5 4.5-4.5 4.5 4.5" />
            </svg>
          </button>
          <button class="header-btn-icon" @click="refreshSelectedMessages" :disabled="isLoadingMessages" title="刷新消息">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </button>
          <button class="header-btn-icon" @click="openExportModal" :disabled="isExportCreating" title="导出聊天记录">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
          </button>
          <button
            type="button"
            class="header-btn-icon"
            :class="{ 'header-btn-icon-active': voiceSidebarOpen }"
            :disabled="!selectedContact"
            :aria-pressed="voiceSidebarOpen"
            aria-label="语音转文字"
            title="语音转文字"
            @click="toggleVoiceSidebar"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="8" y="3" width="8" height="12" rx="4" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
            </svg>
          </button>
          <button class="header-btn-icon" :class="{ 'header-btn-icon-active': resourceSidebarOpen }" @click="toggleResourceSidebar" :disabled="!selectedContact" title="查看图片和视频资源">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <circle cx="8.5" cy="9" r="1.5" />
              <path d="M21 15l-5-5L5 20" />
              <path d="M14 7l4 2.5-4 2.5V7z" />
            </svg>
          </button>
          <button class="header-btn-icon" :class="{ 'header-btn-icon-active': messageSearchOpen }" @click="toggleMessageSearch" :title="messageSearchOpen ? '关闭搜索 (Esc)' : '搜索聊天记录 (Ctrl+F)'">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 16 16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.33333 12.6667C10.2789 12.6667 12.6667 10.2789 12.6667 7.33333C12.6667 4.38781 10.2789 2 7.33333 2C4.38781 2 2 4.38781 2 7.33333C2 10.2789 4.38781 12.6667 7.33333 12.6667Z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14 14L11.1 11.1" />
            </svg>
          </button>
          <button class="header-btn-icon" :class="{ 'header-btn-icon-active': timeSidebarOpen }" @click="toggleTimeSidebar" :disabled="!selectedContact || isLoadingMessages" title="按日期定位">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M8 7V3m8 4V3M3 11h18" />
              <rect x="4" y="5" width="16" height="16" rx="2" ry="2" stroke-width="1.8" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 14h2m3 0h2m3 0h2M7 18h2m3 0h2" />
            </svg>
          </button>
          <select
            v-model="messageTypeFilter"
            class="message-filter-select"
            :disabled="isLoadingMessages || searchContext.active"
            :title="searchContext.active ? '上下文模式下暂不可筛选' : '筛选消息类型'"
          >
            <option v-for="opt in messageTypeFilterOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
          <button
            v-if="selectedContact.isGroup"
            type="button"
            class="header-btn-icon"
            :class="{ 'header-btn-icon-active': groupMembersSidebarOpen }"
            :title="groupMembersSidebarOpen ? '关闭群成员' : '更多（群成员）'"
            :aria-label="groupMembersSidebarOpen ? '关闭群成员' : '更多（群成员）'"
            :aria-expanded="groupMembersSidebarOpen"
            aria-controls="group-members-sidebar"
            @click="toggleGroupMembersSidebar"
          >
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="1.8" />
              <circle cx="12" cy="12" r="1.8" />
              <circle cx="19" cy="12" r="1.8" />
            </svg>
          </button>
        </div>
      </div>

      <form v-if="jevSettingsOpen" id="jev-insight-settings" class="jev-settings" @submit.prevent="applyJevSettings()">
        <header class="jev-settings__header">
          <span class="jev-settings__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m12 3-1.1 3.2a6.7 6.7 0 0 1-4.2 4.2L3.5 11.5l3.2 1.1a6.7 6.7 0 0 1 4.2 4.2L12 20l1.1-3.2a6.7 6.7 0 0 1 4.2-4.2l3.2-1.1-3.2-1.1a6.7 6.7 0 0 1-4.2-4.2L12 3Z" />
            </svg>
          </span>
          <div>
            <strong>Jev 消息洞察</strong>
            <span>当前会话设置</span>
          </div>
          <button type="button" class="jev-settings__close" aria-label="关闭设置" @click="jevSettingsOpen = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </header>

        <label class="jev-settings__enable">
          <span>
            <strong>自动分析</strong>
            <small>为对方发来的文本显示概率分类</small>
          </span>
          <input v-model="jevDraftEnabled" class="jev-settings__switch" type="checkbox" aria-label="自动分析本会话">
        </label>

        <fieldset class="jev-settings__field">
          <legend>参考前文</legend>
          <div class="jev-settings__context-row">
            <div class="jev-settings__presets">
              <button
                v-for="count in jevContextPresets"
                :key="count"
                type="button"
                :class="{ 'is-active': Number(jevDraftContextLimit) === count }"
                @click="setJevDraftContextLimit(count)"
              >{{ count }} 条</button>
            </div>
            <input id="jev-context-limit" v-model.number="jevDraftContextLimit" class="jev-settings__number" type="number" min="1" max="100" inputmode="numeric" aria-label="自定义参考前文条数">
          </div>
        </fieldset>
        <label class="jev-settings__prompt">
          <span>关系与性格 <small>可选</small></span>
          <textarea
            v-model="jevDraftPrompt"
            maxlength="2000"
            rows="3"
            placeholder="例如：情侣；对方很在意约定，我偶尔会忘记。"
          />
        </label>
        <p class="jev-settings__note">设置仅用于当前会话。你也可以右键某条消息，单独使用 Jev 分析。</p>
        <div class="jev-settings__actions">
          <button type="button" @click="jevSettingsOpen = false">取消</button>
          <button type="submit">保存</button>
        </div>
      </form>

      <div v-if="jevInsightNotice" class="jev-insight-banner" role="status">
        <span>{{ jevInsightNotice }}</span>
        <button type="button" @click="disableJevInsights">关闭</button>
      </div>

      <div v-if="searchContext.active" class="chat-context-banner px-6 py-2 border-b border-emerald-200 bg-emerald-50 flex items-center gap-3">
        <div class="chat-context-banner-title text-sm text-emerald-900">
          {{ searchContextBannerText }}
        </div>
        <div class="ml-auto flex items-center gap-2">
          <button type="button" class="chat-context-banner-btn text-xs px-3 py-1 rounded-md bg-white border border-emerald-200 hover:bg-emerald-100" @click="exitSearchContext">
            退出定位
          </button>
          <button type="button" class="chat-context-banner-btn2 text-xs px-3 py-1 rounded-md bg-white border border-gray-200 hover:bg-gray-50" @click="refreshSelectedMessages">
            返回最新
          </button>
        </div>
      </div>

      <MessageList :state="state" />

      <form class="chat-composer" @submit.prevent="openFeatureUnavailableDialog">
        <textarea
          class="chat-composer-input"
          rows="2"
          aria-label="输入要发送的微信消息"
        />
        <div class="chat-composer-toolbar">
          <button type="submit" class="chat-composer-send">发送</button>
        </div>
      </form>

      <button
        v-if="showJumpToBottom"
        type="button"
        class="jump-to-bottom-btn absolute bottom-32 right-6 z-20 w-10 h-10 rounded-full border shadow flex items-center justify-center"
        title="回到最新"
        @click="scrollToBottom"
      >
        <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
    </div>

    <div v-else class="conversation-empty flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-[#03C160]/10 to-[#03C160]/5 flex items-center justify-center">
          <svg class="w-10 h-10 text-[#03C160]/60" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 19.8C17.52 19.8 22 15.99 22 11.3C22 6.6 17.52 2.8 12 2.8C6.48 2.8 2 6.6 2 11.3C2 13.29 2.8 15.12 4.15 16.57C4.6 17.05 4.82 17.29 4.92 17.44C5.14 17.79 5.21 17.99 5.23 18.4C5.24 18.59 5.22 18.81 5.16 19.26C5.1 19.75 5.07 19.99 5.13 20.16C5.23 20.49 5.53 20.71 5.87 20.72C6.04 20.72 6.27 20.63 6.72 20.43L8.07 19.86C8.43 19.71 8.61 19.63 8.77 19.59C8.95 19.55 9.04 19.54 9.22 19.54C9.39 19.53 9.64 19.57 10.14 19.65C10.74 19.75 11.37 19.8 12 19.8Z"/>
          </svg>
        </div>
        <h3 class="conversation-empty-title text-base font-medium mb-1.5">选择一个会话</h3>
        <p class="conversation-empty-text text-sm">
          从左侧列表选择联系人查看聊天记录
        </p>
        <button v-if="selectedAccount" type="button" class="mt-5 rounded-lg border px-4 py-2 text-sm" :aria-pressed="aiSidebarOpen" @click="toggleAiSidebar">向全部聊天提问</button>
      </div>
    </div>

    <GuideDialog
      :open="groupAnnouncementOpen"
      eyebrow=""
      title="群公告"
      description=""
      primary-label="关闭"
      tone="info"
      @primary="closeGroupAnnouncement"
      @close="closeGroupAnnouncement"
    >
      <p
        class="whitespace-pre-wrap break-words text-sm leading-7 text-[#3f4a44]"
        :class="{ 'privacy-blur': privacyMode }"
      >{{ groupAnnouncement }}</p>
    </GuideDialog>
  </div>
</template>

<script>
import { defineComponent } from 'vue'
import MessageList from '~/components/chat/MessageList.vue'

export default defineComponent({
  name: 'ConversationPane',
  components: { MessageList },
  props: {
    state: { type: Object, required: true }
  },
  setup(props) {
    return {
      ...props.state
    }
  }
})
</script>

<style scoped>
/* 侧栏打开后给工具栏单独一行，保留聊天内容空间，避免会话名被挤成竖排。 */
@media (min-width: 1001px) and (max-width: 1440px) {
  .chat-header-ai { height: auto; min-height: 56px; flex-shrink: 0; flex-wrap: wrap; gap: 4px; padding-top: 8px; padding-bottom: 8px; }
  .chat-header-ai > div:first-child { width: 100%; }
  .chat-header-ai > div:last-child { margin-left: 0; flex-wrap: wrap; }
}
.header-btn-jev { position:relative; }
.header-btn-jev__dot { position:absolute; top:5px; right:5px; width:5px; height:5px; border:1px solid var(--chat-header-bg, #ededed); border-radius:50%; background:#07c160; }
.jev-settings { position:absolute; z-index:45; top:48px; right:16px; display:grid; gap:14px; width:min(360px, calc(100% - 32px)); padding:16px; border:1px solid var(--app-border, #dfe3e0); border-radius:12px; background:var(--app-surface-bg, #fff); box-shadow:0 12px 36px #00000024; color:var(--app-text-primary, #252a27); font-size:12px; }
.jev-settings__header { display:flex; align-items:center; gap:10px; padding-bottom:12px; border-bottom:1px solid var(--app-border, #e5e7e6); }
.jev-settings__icon { display:grid; flex:none; width:32px; height:32px; place-items:center; border-radius:8px; background:color-mix(in srgb, #07c160 11%, var(--app-surface-bg, #fff)); color:#079b57; }
.jev-settings__icon svg { width:17px; height:17px; }
.jev-settings__header div { display:grid; min-width:0; gap:1px; }
.jev-settings__header strong { font-size:13px; font-weight:600; }
.jev-settings__header span { color:var(--app-text-muted, #8a918d); font-size:10px; }
.jev-settings__close { display:grid; width:28px; height:28px; margin-left:auto; padding:0; place-items:center; border:0; border-radius:6px; background:transparent; color:var(--app-text-muted, #7b827e); cursor:pointer; }
.jev-settings__close:hover { background:var(--app-list-hover, #f1f2f1); color:var(--app-text-primary, #252a27); }
.jev-settings__close svg { width:15px; height:15px; }
.jev-settings__enable { display:flex; align-items:center; justify-content:space-between; gap:16px; cursor:pointer; }
.jev-settings__enable > span { display:grid; gap:2px; }
.jev-settings__enable strong { font-weight:600; }
.jev-settings__enable small,.jev-settings__note,.jev-settings__prompt small { color:var(--app-text-muted, #7b827e); font-size:10px; font-weight:400; }
.jev-settings__switch { appearance:none; position:relative; flex:none; width:32px; height:18px; margin:0; border:0; border-radius:999px; background:var(--app-border-strong, #c6cbc8); cursor:pointer; transition:background-color .15s ease; }
.jev-settings__switch::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:#fff; box-shadow:0 1px 3px #0003; transition:transform .15s ease; }
.jev-settings__switch:checked { background:#07c160; }
.jev-settings__switch:checked::after { transform:translateX(14px); }
.jev-settings__field { min-width:0; margin:0; padding:0; border:0; }
.jev-settings__field legend,.jev-settings__prompt > span { margin-bottom:7px; font-weight:600; }
.jev-settings__context-row { display:flex; align-items:center; gap:8px; }
.jev-settings__presets { display:flex; min-width:0; flex:1; gap:5px; }
.jev-settings__presets button,.jev-settings__actions button { height:30px; border:1px solid var(--app-border, #dde1de); border-radius:6px; background:var(--app-surface-bg, #fff); color:var(--app-text-primary, #252a27); padding:0 10px; cursor:pointer; font:inherit; }
.jev-settings__presets button { flex:1; padding:0 6px; font-size:11px; }
.jev-settings__presets button:hover,.jev-settings__actions button:hover { background:var(--app-list-hover, #f3f4f3); }
.jev-settings__presets button.is-active { border-color:#8bd8ae; color:#087f48; background:color-mix(in srgb, #07c160 9%, var(--app-surface-bg, #fff)); }
.jev-settings__number { box-sizing:border-box; width:58px; height:30px; border:1px solid var(--app-border, #dde1de); border-radius:6px; background:var(--app-surface-bg, #fff); color:var(--app-text-primary, #252a27); padding:0 7px; font:inherit; }
.jev-settings__prompt { display:grid; }
.jev-settings__prompt textarea { box-sizing:border-box; width:100%; min-height:70px; resize:vertical; border:1px solid var(--app-border, #dde1de); border-radius:7px; outline:0; background:var(--app-surface-bg, #fff); color:var(--app-text-primary, #252a27); padding:8px 10px; font:inherit; font-weight:400; line-height:1.5; }
.jev-settings__prompt textarea:focus,.jev-settings__number:focus { border-color:#07a85a; box-shadow:0 0 0 2px color-mix(in srgb, #07c160 13%, transparent); }
.jev-settings__note { margin:-3px 0 0; line-height:1.55; }
.jev-settings__actions { display:flex; justify-content:flex-end; gap:7px; padding-top:2px; }
.jev-settings__actions button { min-width:62px; }
.jev-settings__actions button[type='submit'] { border-color:#07a85a; background:#07a85a; color:#fff; }
.jev-settings__actions button[type='submit']:hover { border-color:#078d4d; background:#078d4d; }
.jev-insight-banner { display:flex; align-items:center; gap:10px; padding:7px 16px; border-bottom:1px solid #f1d48a; background:#fff8e6; color:#805b12; font-size:12px; }
.jev-insight-banner button { margin-left:auto; border:0; background:transparent; color:inherit; cursor:pointer; font-weight:650; }
:global(html[data-theme='dark']) .jev-insight-banner { border-color:#675626; background:#342f21; color:#e8c970; }
@media (max-width: 640px) { .jev-settings { right:8px; width:calc(100% - 16px); } }
@media (prefers-reduced-motion: reduce) { .jev-settings__switch,.jev-settings__switch::after { transition:none; } }
</style>
