<template>
  <div class="ai-publish-page">
    <aside class="ai-session-sidebar">
      <div class="ai-sidebar-top">
        <div>
          <h2>会话</h2>
        </div>
        <button type="button" class="ai-new-session-btn" @click="createAiConversation">
          <el-icon><Plus /></el-icon>
          <span>新建</span>
        </button>
      </div>

      <div class="ai-session-list">
        <div
          v-for="conversation in sortedAiConversations"
          :key="conversation.id"
          class="ai-session-card ai-session-card-subtle"
          :class="{ active: conversation.id === activeConversationId }"
        >
          <button
            type="button"
            class="ai-session-card-main"
            @click="selectAiConversation(conversation.id)"
          >
            <div class="ai-session-card-top">
              <h3>{{ formatConversationListTitle(conversation.title) }}</h3>
              <span>{{ formatConversationTime(conversation.updatedAt) }}</span>
            </div>
          </button>
          <button
            type="button"
            class="ai-session-delete-btn"
            aria-label="删除对话"
            title="删除对话"
            @click.stop="deleteAiConversation(conversation.id)"
          >
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </div>
    </aside>

    <section class="ai-chat-stage">
      <div class="ai-chat-surface">
        <header class="ai-chat-header">
          <div>
            <h1>{{ activeConversation?.title || 'AI发布' }}</h1>
          </div>
        </header>

        <div ref="aiMessagesViewport" class="ai-message-list">
          <div v-if="isWelcomeConversation" class="ai-empty-state">
            <div class="ai-empty-orb" aria-hidden="true">
              <span class="ai-orb-core"></span>
              <span class="ai-orb-ring ai-orb-ring-a"></span>
              <span class="ai-orb-ring ai-orb-ring-b"></span>
              <span class="ai-orb-ring ai-orb-ring-c"></span>
            </div>
            <div class="ai-empty-copy">
              <h2>这里既能和 AI 纯聊天，也能整理发布任务。</h2>
            </div>
          </div>

          <div
            v-for="message in visibleConversationMessages"
            :key="message.id"
            class="ai-message-row"
            :class="message.role"
          >
            <div
              class="ai-message-avatar"
              :class="message.role === 'assistant' ? 'ai-orb-avatar' : 'ai-user-avatar'"
            >
              <template v-if="message.role === 'assistant'">
                <span class="ai-orb-core"></span>
                <span class="ai-orb-ring ai-orb-ring-a"></span>
                <span class="ai-orb-ring ai-orb-ring-b"></span>
                <span class="ai-orb-ring ai-orb-ring-c"></span>
              </template>
              <template v-else>你</template>
            </div>

            <article
              class="ai-message-bubble"
              :class="message.role === 'assistant' ? 'assistant-flow' : 'user-card'"
            >
              <div class="ai-message-meta">
                <strong>{{ message.role === 'assistant' ? 'AI发布助手' : '你' }}</strong>
                <span>{{ formatMessageTime(message.createdAt) }}</span>
              </div>

              <div v-if="message.attachments?.length" class="ai-message-attachments">
                <div
                  v-for="(attachment, attachmentIndex) in message.attachments"
                  :key="`${message.id}-${attachment.relativePath || attachmentIndex}`"
                  class="ai-message-attachment-chip"
                  :title="attachment.originalName || formatMessageAttachmentLabel(attachment, attachmentIndex)"
                >
                  <span class="ai-message-attachment-icon">
                    {{ formatAttachmentBadge(attachment.category || attachment.mimeType) }}
                  </span>
                  <span class="ai-message-attachment-name">
                    {{ formatMessageAttachmentLabel(attachment, attachmentIndex) }}
                  </span>
                </div>
              </div>

              <p v-if="message.content">{{ message.content }}</p>
            </article>
          </div>
        </div>

        <footer class="ai-composer">
          <div class="ai-composer-float">
            <input
              ref="attachmentInputRef"
              type="file"
              accept="image/*,audio/*,video/*"
              multiple
              class="ai-attachment-input"
              @change="handleAttachmentSelection"
            />

            <div v-if="pendingAttachments.length" class="ai-pending-attachments">
              <div
                v-for="attachment in pendingAttachments"
                :key="attachment.relativePath"
                class="ai-pending-attachment-card"
              >
                <img
                  v-if="isImageAttachment(attachment)"
                  :src="attachment.localPreviewUrl"
                  :alt="attachment.originalName"
                  class="ai-pending-attachment-thumb"
                />
                <div v-else class="ai-pending-attachment-file">
                  <span class="ai-pending-attachment-badge">
                    {{ formatAttachmentBadge(attachment.category || attachment.mimeType) }}
                  </span>
                  <span class="ai-pending-attachment-label">
                    {{ formatMessageAttachmentLabel(attachment) }}
                  </span>
                </div>
                <button
                  type="button"
                  class="ai-pending-attachment-remove"
                  @click="removePendingAttachment(attachment.relativePath)"
                >
                  ×
                </button>
              </div>
            </div>

            <div class="ai-composer-main">
              <button
                type="button"
                class="ai-tool-button"
                :disabled="isStreamingAnyConversation"
                title="上传图片、音频或视频"
                @click="triggerAttachmentSelection"
              >
                <el-icon><Plus /></el-icon>
              </button>

              <div class="ai-composer-input-wrap">
                <el-input
                  v-model="composerText"
                  type="textarea"
                  resize="none"
                  :autosize="{ minRows: 2, maxRows: 8 }"
                  placeholder="例如：帮我把这个作品整理成一条待确认的发布任务。"
                  @keydown.enter.exact.prevent="sendAiMessage"
                />
              </div>

              <button
                type="button"
                class="ai-composer-send-orb"
                :disabled="(!composerText.trim() && !pendingAttachments.length) || isStreamingAnyConversation"
                @click="sendAiMessage"
              >
                <span class="ai-orb-core"></span>
                <span class="ai-orb-ring ai-orb-ring-a"></span>
                <span class="ai-orb-ring ai-orb-ring-b"></span>
                <span class="ai-orb-ring ai-orb-ring-c"></span>
              </button>
            </div>

            <div class="ai-composer-actions">
              <span>Enter 发送，Shift + Enter 换行</span>
            </div>
          </div>
        </footer>

        <transition name="ai-task-preview-float">
          <aside
            v-if="activeConversation?.taskPreview && taskPreviewPanelVisible"
            class="ai-task-preview-popover"
          >
            <article
              class="ai-task-preview-sheet"
              :class="{ 'is-ready': activeConversation.taskPreview.ready }"
            >
              <div class="ai-task-preview-head">
                <div>
                  <h3>待确认发布任务</h3>
                  <p>
                    {{
                      activeConversation.taskPreview.ready
                        ? '信息已齐，可以直接确认发布。'
                        : '信息还不完整，先继续和 AI 补充。'
                    }}
                  </p>
                </div>
                <span class="ai-task-preview-status">
                  {{ activeConversation.taskPreview.ready ? '可发布' : '待补全' }}
                </span>
              </div>

              <div class="ai-task-preview-grid">
                <div class="ai-task-preview-field">
                  <span>账号</span>
                  <strong>{{ formatPreviewAccounts(activeConversation.taskPreview.accounts) }}</strong>
                </div>
                <div class="ai-task-preview-field">
                  <span>作品</span>
                  <strong>{{ formatPreviewWorks(activeConversation.taskPreview.works) }}</strong>
                </div>
                <div class="ai-task-preview-field">
                  <span>标题</span>
                  <strong>{{ activeConversation.taskPreview.title || '待补全' }}</strong>
                </div>
                <div class="ai-task-preview-field">
                  <span>发布时间</span>
                  <strong>{{ formatPreviewSchedule(activeConversation.taskPreview) }}</strong>
                </div>
              </div>

              <div v-if="activeConversation.taskPreview.content" class="ai-task-preview-content">
                {{ activeConversation.taskPreview.content }}
              </div>

              <div
                v-if="activeConversation.taskPreview.missingFields?.length"
                class="ai-task-preview-missing"
              >
                仍缺：{{ activeConversation.taskPreview.missingFields.join('、') }}
              </div>

              <div class="ai-task-preview-actions">
                <el-button
                  type="primary"
                  :disabled="!activeConversation.taskPreview.ready || confirmingTaskPreview"
                  :loading="confirmingTaskPreview"
                  @click="confirmTaskPreview"
                >
                  确认发布
                </el-button>
                <el-button :disabled="confirmingTaskPreview" @click="clearTaskPreview">
                  清除任务卡片
                </el-button>
              </div>
            </article>
          </aside>
        </transition>

        <button
          v-if="activeConversation?.taskPreview"
          type="button"
          class="ai-task-preview-fab"
          :class="{
            'is-ready': activeConversation.taskPreview.ready,
            'is-open': taskPreviewPanelVisible,
          }"
          @click="toggleTaskPreviewPanel"
        >
          <span class="ai-task-preview-fab-status">
            {{ activeConversation.taskPreview.ready ? '可发布' : '待补全' }}
          </span>
          <strong>{{ taskPreviewPanelVisible ? '收起发布任务' : '查看发布任务' }}</strong>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Close, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { aiPublishApi } from '@/api/aiPublish'
import { usePublishTaskStore } from '@/stores/publishTask'

const AI_PUBLISH_STORAGE_KEY = 'sau_ai_publish_state_v2'
const publishTaskStore = usePublishTaskStore()
const conversations = ref([])
const activeConversationId = ref('')
const composerText = ref('')
const aiMessagesViewport = ref(null)
const attachmentInputRef = ref(null)
const confirmingTaskPreview = ref(false)
const hasLoadedAiPublishState = ref(false)
const hasApiKey = ref(false)
const activeChatTaskId = ref('')
const pendingAttachments = ref([])
const taskPreviewPanelVisible = ref(false)
const aiConfigForm = reactive({
  provider: 'deepseek',
  apiBase: 'https://api.deepseek.com/v1',
  apiKey: '',
  defaultModel: 'deepseek-chat',
})

let aiChatEventSource = null

const createId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `ai-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`
}

const formatNowIso = () => new Date().toISOString()

const countCjkChars = (text) => (
  Array.from(String(text || '')).filter((char) => char >= '\u4e00' && char <= '\u9fff').length
)

const countSuspiciousMojibakeChars = (text) => Array.from(String(text || '')).filter((char) => {
  const code = char.charCodeAt(0)
  return (code >= 0x80 && code <= 0xff) || char === '\uFFFD'
}).length

const repairMojibakeSegment = (text) => {
  if (!text || countSuspiciousMojibakeChars(text) === 0) {
    return text
  }

  try {
    const bytes = Uint8Array.from(Array.from(text), (char) => char.charCodeAt(0))
    const candidate = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
    if (countCjkChars(candidate) > countCjkChars(text)) {
      return candidate
    }
    if (countSuspiciousMojibakeChars(candidate) < countSuspiciousMojibakeChars(text)) {
      return candidate
    }
  } catch (error) {
    return text
  }

  return text
}

const repairPossibleMojibake = (value) => {
  const text = String(value ?? '')
  if (!text) {
    return text
  }

  const wholeCandidate = repairMojibakeSegment(text)
  if (wholeCandidate !== text) {
    return wholeCandidate
  }

  if (countSuspiciousMojibakeChars(text) === 0) {
    return text
  }

  const chunks = []
  let byteRun = ''
  for (const char of Array.from(text)) {
    if (char.charCodeAt(0) <= 0xff) {
      byteRun += char
      continue
    }
    if (byteRun) {
      chunks.push(repairMojibakeSegment(byteRun))
      byteRun = ''
    }
    chunks.push(char)
  }

  if (byteRun) {
    chunks.push(repairMojibakeSegment(byteRun))
  }

  return chunks.join('')
}

const repairTaskPreview = (taskPreview) => {
  if (!taskPreview || typeof taskPreview !== 'object') {
    return taskPreview || null
  }

  return {
    ...taskPreview,
    title: repairPossibleMojibake(taskPreview.title || ''),
    content: repairPossibleMojibake(taskPreview.content || ''),
    scheduleTime: repairPossibleMojibake(taskPreview.scheduleTime || ''),
    missingFields: Array.isArray(taskPreview.missingFields) ? taskPreview.missingFields : [],
    tags: Array.isArray(taskPreview.tags)
      ? taskPreview.tags.map((item) => repairPossibleMojibake(item))
      : [],
    accounts: Array.isArray(taskPreview.accounts)
      ? taskPreview.accounts.map((account) => ({
        ...account,
        name: repairPossibleMojibake(account?.name || ''),
        platform: repairPossibleMojibake(account?.platform || ''),
      }))
      : [],
    works: Array.isArray(taskPreview.works)
      ? taskPreview.works.map((work) => ({
        ...work,
        name: repairPossibleMojibake(work?.name || ''),
        kind: repairPossibleMojibake(work?.kind || ''),
        filePath: repairPossibleMojibake(work?.filePath || ''),
      }))
      : [],
  }
}

const repairStoredAttachment = (attachment) => ({
  relativePath: String(attachment?.relativePath || ''),
  originalName: repairPossibleMojibake(attachment?.originalName || ''),
  mimeType: String(attachment?.mimeType || ''),
  sizeBytes: Number(attachment?.sizeBytes || 0),
  category: String(attachment?.category || ''),
})

const repairStoredConversation = (conversation) => ({
  ...conversation,
  title: repairPossibleMojibake(conversation?.title || ''),
  messages: Array.isArray(conversation?.messages)
    ? conversation.messages.map((message) => ({
      ...message,
      content: repairPossibleMojibake(message?.content || ''),
      attachments: Array.isArray(message?.attachments)
        ? message.attachments.map(repairStoredAttachment)
        : [],
    }))
    : [],
  taskPreview: repairTaskPreview(conversation?.taskPreview || null),
})

const buildAssistantWelcomeMessage = () => ({
  id: createId(),
  role: 'assistant',
  kind: 'welcome',
  content:
    '你好，我是这个项目里的 AI 助手。你可以先正常和我聊天、问项目问题、发图片给我看；只有你明确提到要发布时，我才会帮你整理发布任务。',
  createdAt: formatNowIso(),
})

const sanitizeMessageAttachments = (attachments) => (
  (Array.isArray(attachments) ? attachments : [])
    .map((attachment) => ({
      relativePath: String(attachment?.relativePath || ''),
      originalName: String(attachment?.originalName || ''),
      mimeType: String(attachment?.mimeType || ''),
      sizeBytes: Number(attachment?.sizeBytes || 0),
      category: String(attachment?.category || ''),
    }))
    .filter((attachment) => attachment.relativePath)
)

const resolveAttachmentCategory = (value) => {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'image' || normalized.startsWith('image/')) {
    return 'image'
  }
  if (normalized === 'audio' || normalized.startsWith('audio/')) {
    return 'audio'
  }
  if (normalized === 'video' || normalized.startsWith('video/')) {
    return 'video'
  }
  return 'file'
}

const isImageAttachment = (attachment) => (
  resolveAttachmentCategory(attachment?.category || attachment?.mimeType) === 'image'
)

const formatAttachmentBadge = (value) => {
  const category = resolveAttachmentCategory(value)
  if (category === 'audio') {
    return '音'
  }
  if (category === 'video') {
    return '视'
  }
  if (category === 'image') {
    return '图'
  }
  return '附'
}

const formatMessageAttachmentLabel = (attachment, index = 0) => {
  const originalName = String(attachment?.originalName || '').trim()
  if (originalName) {
    return originalName
  }

  const category = resolveAttachmentCategory(attachment?.category || attachment?.mimeType)
  if (category === 'audio') {
    return `音频 ${index + 1}`
  }
  if (category === 'video') {
    return `视频 ${index + 1}`
  }
  if (category === 'image') {
    return `图片 ${index + 1}`
  }
  return `附件 ${index + 1}`
}

const buildMessage = (role, content = '', attachments = []) => ({
  id: createId(),
  role,
  kind: 'message',
  content,
  attachments: sanitizeMessageAttachments(attachments),
  createdAt: formatNowIso(),
})

const deriveConversationTitle = (content) => {
  const normalized = String(content || '').replace(/\s+/g, ' ').trim()
  if (!normalized) {
    return '新对话'
  }
  return normalized.length > 18 ? `${normalized.slice(0, 18)}...` : normalized
}

const formatConversationListTitle = (title) => {
  const normalized = String(title || '').replace(/\s+/g, ' ').trim()
  if (!normalized) {
    return '新对话'
  }
  return normalized.length > 8 ? normalized.slice(0, 8) : normalized
}

const buildConversation = () => {
  const createdAt = formatNowIso()
  return {
    id: createId(),
    title: '新对话',
    createdAt,
    updatedAt: createdAt,
    messages: [buildAssistantWelcomeMessage()],
    taskPreview: null,
    isStreaming: false,
  }
}

const sortConversationsByUpdatedAt = (items) => (
  [...items].sort((left, right) => (
    new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
  ))
)

const resolveConversationId = (items, preferredId = '') => {
  if (preferredId && items.some((conversation) => conversation.id === preferredId)) {
    return preferredId
  }
  return sortConversationsByUpdatedAt(items)[0]?.id || ''
}

const activeConversation = computed(() => (
  conversations.value.find((conversation) => conversation.id === activeConversationId.value) || null
))

const activeTaskPreview = computed(() => activeConversation.value?.taskPreview || null)
const activeConversationMessages = computed(() => activeConversation.value?.messages || [])
const visibleConversationMessages = computed(() => {
  if (isWelcomeConversation.value) {
    return activeConversationMessages.value.filter((message) => message.kind !== 'welcome')
  }
  return activeConversationMessages.value
})
const sortedAiConversations = computed(() => sortConversationsByUpdatedAt(conversations.value))
const isWelcomeConversation = computed(() => {
  if (!activeConversation.value) {
    return false
  }
  return activeConversation.value.messages.filter((message) => message.role === 'user').length === 0
})
const isStreamingAnyConversation = computed(() => (
  conversations.value.some((conversation) => conversation.isStreaming)
))

const scrollAiMessagesToBottom = async () => {
  await nextTick()
  const viewport = aiMessagesViewport.value
  if (!viewport) {
    return
  }
  viewport.scrollTop = viewport.scrollHeight
}

const saveAiPublishState = () => {
  if (!hasLoadedAiPublishState.value || typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(
    AI_PUBLISH_STORAGE_KEY,
    JSON.stringify({
      conversations: conversations.value,
      activeConversationId: activeConversationId.value,
      composerText: composerText.value,
    }),
  )
}

const loadAiPublishState = () => {
  const seededConversation = buildConversation()
  if (typeof window === 'undefined') {
    conversations.value = [seededConversation]
    activeConversationId.value = seededConversation.id
    hasLoadedAiPublishState.value = true
    return
  }

  const rawState = window.localStorage.getItem(AI_PUBLISH_STORAGE_KEY)
  if (!rawState) {
    conversations.value = [seededConversation]
    activeConversationId.value = seededConversation.id
    hasLoadedAiPublishState.value = true
    return
  }

  try {
    const parsedState = JSON.parse(rawState)
    const storedConversations = Array.isArray(parsedState?.conversations)
      ? parsedState.conversations
      : []
    if (storedConversations.length === 0) {
      conversations.value = [seededConversation]
      activeConversationId.value = seededConversation.id
    } else {
      conversations.value = storedConversations.map((conversation) => ({
        ...repairStoredConversation(conversation),
        taskPreview: repairTaskPreview(conversation.taskPreview || null),
        isStreaming: false,
      }))
      activeConversationId.value = resolveConversationId(
        storedConversations,
        String(parsedState?.activeConversationId || ''),
      )
      composerText.value = repairPossibleMojibake(parsedState?.composerText || '')
    }
  } catch (error) {
    console.error('Failed to load AI publish state:', error)
    conversations.value = [seededConversation]
    activeConversationId.value = seededConversation.id
  }

  hasLoadedAiPublishState.value = true
}

const mutateConversation = (conversationId, mutate) => {
  const targetConversation = conversations.value.find((conversation) => conversation.id === conversationId)
  if (!targetConversation) {
    return null
  }
  mutate(targetConversation)
  targetConversation.updatedAt = formatNowIso()
  return targetConversation
}

const appendMessageToConversation = (conversationId, message) => {
  mutateConversation(conversationId, (conversation) => {
    conversation.messages.push(message)
  })
}

const createAiConversation = () => {
  const conversation = buildConversation()
  conversations.value = [conversation, ...conversations.value]
  activeConversationId.value = conversation.id
  composerText.value = ''
  scrollAiMessagesToBottom()
  return conversation
}

const selectAiConversation = (conversationId) => {
  activeConversationId.value = conversationId
  scrollAiMessagesToBottom()
}

const deleteAiConversation = (conversationId) => {
  const deletingActiveConversation = activeConversationId.value === conversationId
  const remainingConversations = conversations.value.filter((conversation) => conversation.id !== conversationId)

  if (remainingConversations.length === 0) {
    const seededConversation = buildConversation()
    conversations.value = [seededConversation]
    activeConversationId.value = seededConversation.id
    composerText.value = ''
    scrollAiMessagesToBottom()
    return
  }

  conversations.value = remainingConversations
  if (
    deletingActiveConversation ||
    !remainingConversations.some((conversation) => conversation.id === activeConversationId.value)
  ) {
    activeConversationId.value = resolveConversationId(remainingConversations)
    composerText.value = ''
  }
}

const closeChatEventSource = () => {
  if (aiChatEventSource) {
    aiChatEventSource.close()
    aiChatEventSource = null
  }
  activeChatTaskId.value = ''
}

const revokeAttachmentPreview = (attachment) => {
  if (attachment?.localPreviewUrl) {
    URL.revokeObjectURL(attachment.localPreviewUrl)
  }
}

const triggerAttachmentSelection = () => {
  attachmentInputRef.value?.click()
}

const removePendingAttachment = (relativePath) => {
  const target = pendingAttachments.value.find((attachment) => attachment.relativePath === relativePath)
  revokeAttachmentPreview(target)
  pendingAttachments.value = pendingAttachments.value.filter(
    (attachment) => attachment.relativePath !== relativePath,
  )
}

const handleAttachmentSelection = async (event) => {
  const files = Array.from(event?.target?.files || [])
  if (!files.length) {
    return
  }

  for (const file of files) {
    try {
      const response = await aiPublishApi.uploadAttachment(file)
      const category = resolveAttachmentCategory(response.data?.category || file.type)
      pendingAttachments.value.push({
        ...response.data,
        category,
        localPreviewUrl: category === 'image' ? URL.createObjectURL(file) : '',
      })
    } catch (error) {
      console.error('upload ai publish attachment failed:', error)
      ElMessage.error(error?.message || `${file.name} 上传失败`)
    }
  }

  if (event?.target) {
    event.target.value = ''
  }
}

const loadAiPublishConfig = async () => {
  try {
    const response = await aiPublishApi.loadConfig()
    aiConfigForm.defaultModel = response.data.defaultModel || 'deepseek-chat'
    hasApiKey.value = Boolean(response.data.hasApiKey)
  } catch (error) {
    console.error('load ai publish config failed:', error)
    hasApiKey.value = false
  }
}

const buildChatRequestMessages = (conversation) => {
  const candidateMessages = (conversation?.messages || [])
    .filter((message) => message.role === 'user' || message.role === 'assistant')
    .filter(
      (message) =>
        String(message.content || '').trim() ||
        (Array.isArray(message.attachments) && message.attachments.length),
    )

  let lastUserMessageId = ''
  for (let index = candidateMessages.length - 1; index >= 0; index -= 1) {
    if (candidateMessages[index]?.role === 'user') {
      lastUserMessageId = String(candidateMessages[index]?.id || '')
      break
    }
  }

  return candidateMessages.map((message) => ({
    role: message.role,
    content: message.content,
    attachments:
      message.role === 'user' && String(message.id || '') === lastUserMessageId
        ? sanitizeMessageAttachments(message.attachments)
        : [],
  }))
}

const startAiChat = async (conversation, assistantMessage) => {
  const requestMessages = buildChatRequestMessages(conversation)
  const response = await aiPublishApi.startChat({
    conversationId: conversation.id,
    model: aiConfigForm.defaultModel,
    messages: requestMessages,
  })
  const taskId = response.data.taskId
  activeChatTaskId.value = taskId

  mutateConversation(conversation.id, (targetConversation) => {
    targetConversation.isStreaming = true
  })

  closeChatEventSource()
  activeChatTaskId.value = taskId
  const eventSource = new EventSource(aiPublishApi.getChatTaskStreamUrl(taskId))
  aiChatEventSource = eventSource

  eventSource.addEventListener('assistant-delta', (event) => {
    const payload = JSON.parse(event.data)
    mutateConversation(conversation.id, (targetConversation) => {
      const targetMessage = targetConversation.messages.find((message) => message.id === assistantMessage.id)
      if (targetMessage) {
        targetMessage.content = repairPossibleMojibake(
          `${targetMessage.content || ''}${payload.delta || ''}`,
        )
      }
    })
    scrollAiMessagesToBottom()
  })

  eventSource.addEventListener('assistant-finished', () => {
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.isStreaming = false
    })
  })

  eventSource.addEventListener('task-preview', (event) => {
    const payload = JSON.parse(event.data)
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.taskPreview = repairTaskPreview(payload)
    })
    taskPreviewPanelVisible.value = true
  })

  eventSource.addEventListener('task-finished', () => {
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.isStreaming = false
    })
    closeChatEventSource()
  })

  eventSource.addEventListener('task-error', (event) => {
    const payload = JSON.parse(event.data)
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.isStreaming = false
      const targetMessage = targetConversation.messages.find((message) => message.id === assistantMessage.id)
      if (targetMessage && !targetMessage.content) {
        targetMessage.content = payload.message || 'AI 请求失败'
      }
    })
    ElMessage.error(payload.message || 'AI 请求失败')
    closeChatEventSource()
  })

  eventSource.onerror = () => {
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.isStreaming = false
    })
    closeChatEventSource()
  }
}

const sendAiMessage = async () => {
  const prompt = composerText.value.trim()
  const outgoingAttachments = pendingAttachments.value.map((attachment) => ({
    relativePath: attachment.relativePath,
    originalName: attachment.originalName,
    mimeType: attachment.mimeType,
    sizeBytes: attachment.sizeBytes,
    category: attachment.category,
  }))

  if (!prompt && outgoingAttachments.length === 0) {
    return
  }

  // 先到关于页接入 API
  if (!hasApiKey.value) {
    ElMessage.warning('先到关于页接入 API')
    return
  }

  if (isStreamingAnyConversation.value) {
    ElMessage.warning('当前已有 AI 回复在生成中，请稍后再发。')
    return
  }

  const conversation = activeConversation.value || createAiConversation()
  appendMessageToConversation(conversation.id, buildMessage('user', prompt, outgoingAttachments))

  mutateConversation(conversation.id, (targetConversation) => {
    const userMessages = targetConversation.messages.filter((message) => message.role === 'user')
    if (userMessages.length === 1 && targetConversation.title === '新对话') {
      targetConversation.title = deriveConversationTitle(
        prompt || outgoingAttachments[0]?.originalName || '附件消息',
      )
    }
  })

  composerText.value = ''
  pendingAttachments.value.forEach(revokeAttachmentPreview)
  pendingAttachments.value = []
  const assistantMessage = buildMessage('assistant', '')
  appendMessageToConversation(conversation.id, assistantMessage)
  scrollAiMessagesToBottom()

  try {
    await startAiChat(
      conversations.value.find((item) => item.id === conversation.id),
      assistantMessage,
    )
  } catch (error) {
    console.error('start ai chat failed:', error)
    mutateConversation(conversation.id, (targetConversation) => {
      targetConversation.isStreaming = false
      const targetMessage = targetConversation.messages.find((message) => message.id === assistantMessage.id)
      if (targetMessage) {
        targetMessage.content = error?.message || 'AI 服务启动失败'
      }
    })
    closeChatEventSource()
  }
}

const clearTaskPreview = () => {
  if (!activeConversation.value) {
    return
  }
  mutateConversation(activeConversation.value.id, (conversation) => {
    conversation.taskPreview = null
  })
  taskPreviewPanelVisible.value = false
}

const toggleTaskPreviewPanel = () => {
  if (!activeTaskPreview.value) {
    return
  }
  taskPreviewPanelVisible.value = !taskPreviewPanelVisible.value
}

const confirmTaskPreview = async () => {
  if (!activeConversation.value?.taskPreview) {
    return
  }
  confirmingTaskPreview.value = true
  try {
    const response = await aiPublishApi.confirmTask({
      conversationId: activeConversation.value.id,
      task: activeConversation.value.taskPreview,
    })
    const publishTaskId = response.data?.publishTaskId
    if (publishTaskId) {
      publishTaskStore.trackTask({
        taskId: publishTaskId,
        label: activeConversation.value.title || 'AI 发布任务',
        mode: 'ai-publish',
      })
    }
    taskPreviewPanelVisible.value = false
    ElMessage.success('发布任务已进入任务进度。')
  } catch (error) {
    console.error('confirm ai publish task failed:', error)
    ElMessage.error(error?.message || '确认发布失败')
  } finally {
    confirmingTaskPreview.value = false
  }
}

const formatPreviewAccounts = (accounts) => {
  if (!Array.isArray(accounts) || accounts.length === 0) {
    return '待补全'
  }
  return accounts
    .map((account) => account.name || account.platform || '未命名账号')
    .join('、')
}

const formatPreviewWorks = (works) => {
  if (!Array.isArray(works) || works.length === 0) {
    return '待补全'
  }
  return works
    .map((work) => work.name || work.filePath || '未命名作品')
    .join('、')
}

const formatPreviewSchedule = (taskPreview) => {
  if (!taskPreview) {
    return '待补全'
  }
  if (taskPreview.scheduleType === 'scheduled' && taskPreview.scheduleTime) {
    return taskPreview.scheduleTime
  }
  if (taskPreview.scheduleType === 'now') {
    return '立即发布'
  }
  return '待补全'
}

const formatConversationTime = (value) => {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  const now = new Date()
  return date.toDateString() === now.toDateString()
    ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

const formatMessageTime = (value) => (
  new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
)

watch(
  [conversations, activeConversationId, composerText],
  () => {
    saveAiPublishState()
  },
  { deep: true },
)

watch(
  activeConversationMessages,
  () => {
    scrollAiMessagesToBottom()
  },
  { deep: true },
)

watch(
  activeTaskPreview,
  (value) => {
    if (!value) {
      taskPreviewPanelVisible.value = false
    }
  },
  { deep: true },
)

onMounted(async () => {
  loadAiPublishState()
  await loadAiPublishConfig()
  scrollAiMessagesToBottom()
})

onBeforeUnmount(() => {
  pendingAttachments.value.forEach(revokeAttachmentPreview)
  closeChatEventSource()
})
</script>

<style scoped lang="scss">
.ai-publish-page {
  height: calc(100vh - 40px);
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
  padding: 4px 0;
  color: #1c1917;
}

.ai-session-sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 14px;
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(250, 250, 249, 0.92) 100%);
  border: 1px solid rgba(231, 229, 228, 0.95);
  box-shadow:
    rgba(14, 63, 126, 0.04) 0 0 0 1px,
    rgba(42, 51, 69, 0.04) 0 1px 1px -0.5px,
    rgba(42, 51, 70, 0.04) 0 6px 18px -8px;
}

.ai-sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 14px;
}

.ai-sidebar-label {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #a8a29e;
}

.ai-sidebar-top h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  line-height: 1;
  color: #292524;
}

.ai-new-session-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 999px;
  background: #f5f5f4;
  color: #44403c;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-new-session-btn:hover {
  background: #e7e5e4;
}

.ai-session-list {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}

.ai-session-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 20px;
  transition: all 0.2s ease;
}

.ai-session-card-subtle {
  border: 1px solid rgba(231, 229, 228, 0.92);
  background: rgba(255, 255, 255, 0.84);
}

.ai-session-card.active {
  border-color: rgba(148, 163, 184, 0.42);
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    rgba(14, 63, 126, 0.04) 0 0 0 1px,
    rgba(42, 51, 69, 0.04) 0 1px 1px -0.5px,
    rgba(42, 51, 70, 0.08) 0 8px 18px -10px;
}

.ai-session-card-main {
  flex: 1;
  border: 0;
  background: transparent;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.ai-session-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ai-session-card-top h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: #292524;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-session-card-top span {
  font-size: 12px;
  color: #a8a29e;
  white-space: nowrap;
}

.ai-session-delete-btn {
  width: 30px;
  min-width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  background: #f5f5f4;
  color: #78716c;
  cursor: pointer;
}

.ai-chat-stage {
  min-height: 0;
  position: relative;
}

.ai-chat-surface {
  position: relative;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 20px 26px;
  border-radius: 32px;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.9), rgba(245, 245, 244, 0.96)),
    #f5f5f4;
  border: 1px solid rgba(231, 229, 228, 0.95);
  box-shadow:
    rgba(14, 63, 126, 0.04) 0 0 0 1px,
    rgba(42, 51, 69, 0.04) 0 1px 1px -0.5px,
    rgba(42, 51, 70, 0.08) 0 12px 24px -12px;
}

.ai-chat-header {
  margin-bottom: 16px;
}

.ai-chat-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #a8a29e;
}

.ai-chat-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
  color: #1c1917;
}

.ai-chat-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: #78716c;
}

.ai-message-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 6px 6px 14px 2px;
}

.ai-empty-state {
  margin: auto 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 18px;
  padding: 30px 24px 12px;
}

.ai-empty-orb,
.ai-orb-avatar,
.ai-composer-send-orb {
  position: relative;
  display: inline-grid;
  place-items: center;
  overflow: hidden;
  border-radius: 999px;
  background: #cff1f4;
  isolation: isolate;
}

.ai-empty-orb {
  width: 112px;
  height: 112px;
  box-shadow: rgba(17, 12, 46, 0.15) 0 48px 100px 0;
}

.ai-empty-copy h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.5;
  color: #1c1917;
}

.ai-empty-copy p {
  margin: 8px 0 0;
  color: #78716c;
  line-height: 1.65;
}

.ai-suggestion-grid {
  width: 100%;
  max-width: 760px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.ai-suggestion-card {
  border: 1px solid rgba(231, 229, 228, 0.92);
  background: rgba(255, 255, 255, 0.92);
  color: #44403c;
  border-radius: 22px;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-suggestion-card:hover {
  transform: translateY(-1px);
  box-shadow:
    rgba(14, 63, 126, 0.04) 0 0 0 1px,
    rgba(42, 51, 70, 0.08) 0 10px 20px -14px;
}

.ai-message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.ai-message-row.user {
  flex-direction: row-reverse;
}

.ai-message-avatar {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
}

.ai-orb-avatar {
  width: 38px;
  height: 38px;
  box-shadow: rgba(17, 12, 46, 0.1) 0 18px 38px 0;
}

.ai-user-avatar {
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(231, 229, 228, 0.96);
  color: #44403c;
  font-size: 13px;
  font-weight: 600;
}

.ai-orb-core,
.ai-orb-ring {
  position: absolute;
  border-radius: 999px;
  filter: blur(7px);
}

.ai-orb-core {
  inset: 22%;
  background: rgba(158, 159, 239, 0.92);
}

.ai-orb-ring-a {
  width: 48%;
  height: 48%;
  background: rgba(196, 113, 236, 0.9);
  animation: ai-orb-drift-a 5s ease-in-out infinite;
}

.ai-orb-ring-b {
  width: 36%;
  height: 36%;
  background: rgba(155, 199, 97, 0.88);
  animation: ai-orb-drift-b 4.5s ease-in-out infinite;
}

.ai-orb-ring-c {
  width: 30%;
  height: 30%;
  background: rgba(244, 114, 182, 0.88);
  animation: ai-orb-drift-c 5.8s ease-in-out infinite;
}

.ai-message-bubble {
  max-width: min(820px, calc(100% - 64px));
}

.ai-message-bubble.user-card {
  padding: 14px 16px;
  border-radius: 24px;
  border: 1px solid rgba(231, 229, 228, 0.92);
  background: rgba(255, 255, 255, 0.94);
  box-shadow:
    rgba(14, 63, 126, 0.04) 0 0 0 1px,
    rgba(42, 51, 70, 0.08) 0 10px 18px -14px;
}

.ai-message-bubble.assistant-flow {
  padding: 10px 4px 2px 0;
}

.ai-message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.ai-message-meta strong {
  color: #292524;
  font-size: 12px;
  font-weight: 500;
}

.ai-message-meta span {
  color: #a8a29e;
  font-size: 12px;
}

.ai-message-bubble p {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.75;
  font-size: 15px;
  font-weight: 400;
  color: #292524;
}

.ai-message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.ai-message-attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 11px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(231, 229, 228, 0.9);
  color: #57534e;
  font-size: 13px;
}

.ai-message-attachment-icon {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #f5f5f4;
  color: #44403c;
  font-size: 12px;
  font-weight: 700;
}

.ai-composer {
  margin-top: 8px;
}

.ai-composer-float {
  border-radius: 28px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(231, 229, 228, 0.94);
  box-shadow:
    rgba(14, 63, 126, 0.06) 0 0 0 1px,
    rgba(42, 51, 70, 0.06) 0 24px 30px -18px;
}

.ai-attachment-input {
  display: none;
}

.ai-pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.ai-pending-attachment-card {
  position: relative;
  width: 88px;
  height: 88px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(231, 229, 228, 0.94);
  background: #fafaf9;
}

.ai-pending-attachment-thumb,
.ai-pending-attachment-file {
  width: 100%;
  height: 100%;
}

.ai-pending-attachment-thumb {
  object-fit: cover;
}

.ai-pending-attachment-file {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  text-align: center;
}

.ai-pending-attachment-badge {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #f5f5f4;
  color: #44403c;
  font-weight: 700;
}

.ai-pending-attachment-label {
  font-size: 11px;
  line-height: 1.4;
  color: #78716c;
  word-break: break-all;
}

.ai-pending-attachment-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 999px;
  background: rgba(28, 25, 23, 0.76);
  color: #fff;
  cursor: pointer;
}

.ai-composer-main {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.ai-tool-button {
  width: 42px;
  height: 42px;
  border: 0;
  border-radius: 999px;
  background: #f5f5f4;
  color: #57534e;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-tool-button:hover:not(:disabled) {
  background: #e7e5e4;
}

.ai-tool-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ai-composer-input-wrap {
  flex: 1;
}

.ai-composer-input-wrap :deep(.el-textarea__inner) {
  min-height: 54px !important;
  border: 0;
  box-shadow: none;
  background: transparent;
  color: #292524;
  padding: 12px 6px;
  line-height: 1.7;
}

.ai-composer-input-wrap :deep(.el-textarea__inner::placeholder) {
  color: #a8a29e;
}

.ai-composer-send-orb {
  width: 48px;
  height: 48px;
  border: 0;
  cursor: pointer;
  box-shadow: rgba(17, 12, 46, 0.16) 0 20px 40px 0;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.ai-composer-send-orb:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.02);
}

.ai-composer-send-orb:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ai-composer-actions {
  margin-top: 8px;
  padding-left: 54px;
}

.ai-composer-actions span {
  font-size: 12px;
  color: #a8a29e;
}

.ai-task-preview-popover {
  position: absolute;
  right: 18px;
  bottom: 138px;
  width: min(420px, calc(100% - 36px));
  z-index: 20;
}

.ai-task-preview-sheet {
  border-radius: 28px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(231, 229, 228, 0.96);
  box-shadow:
    rgba(14, 63, 126, 0.06) 0 0 0 1px,
    rgba(42, 51, 70, 0.12) 0 26px 40px -18px;
}

.ai-task-preview-sheet.is-ready {
  border-color: rgba(134, 239, 172, 0.8);
}

.ai-task-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ai-task-preview-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: #292524;
}

.ai-task-preview-head p {
  margin: 8px 0 0;
  color: #78716c;
  line-height: 1.65;
}

.ai-task-preview-status {
  white-space: nowrap;
  padding: 7px 12px;
  border-radius: 999px;
  background: #f5f5f4;
  color: #44403c;
  font-size: 12px;
  font-weight: 600;
}

.ai-task-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.ai-task-preview-field,
.ai-task-preview-content,
.ai-task-preview-missing {
  border-radius: 18px;
  background: #fafaf9;
  border: 1px solid rgba(231, 229, 228, 0.72);
}

.ai-task-preview-field {
  padding: 12px;
}

.ai-task-preview-field span {
  display: block;
  margin-bottom: 6px;
  color: #a8a29e;
  font-size: 12px;
}

.ai-task-preview-field strong {
  color: #292524;
  line-height: 1.65;
  word-break: break-word;
}

.ai-task-preview-content,
.ai-task-preview-missing {
  margin-top: 14px;
  padding: 12px 14px;
  line-height: 1.7;
  color: #44403c;
  white-space: pre-wrap;
}

.ai-task-preview-missing {
  color: #b45309;
  background: #fffbeb;
}

.ai-task-preview-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.ai-task-preview-fab {
  position: absolute;
  right: 18px;
  bottom: 18px;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  border: 0;
  border-radius: 999px;
  background: rgba(28, 25, 23, 0.92);
  color: #fff;
  padding: 12px 16px;
  cursor: pointer;
  box-shadow: rgba(17, 12, 46, 0.18) 0 24px 40px -18px;
}

.ai-task-preview-fab.is-ready {
  background: #15803d;
}

.ai-task-preview-fab-status {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  font-size: 12px;
}

.ai-task-preview-float-enter-active,
.ai-task-preview-float-leave-active {
  transition: all 0.2s ease;
}

.ai-task-preview-float-enter-from,
.ai-task-preview-float-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes ai-orb-drift-a {
  0% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(14px, -10px) scale(1.15);
  }
  100% {
    transform: translate(-8px, 10px) scale(0.92);
  }
}

@keyframes ai-orb-drift-b {
  0% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(-12px, 8px) scale(1.1);
  }
  100% {
    transform: translate(10px, -8px) scale(0.9);
  }
}

@keyframes ai-orb-drift-c {
  0% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(10px, 12px) scale(1.18);
  }
  100% {
    transform: translate(-10px, -10px) scale(0.88);
  }
}

@media (max-width: 1200px) {
  .ai-publish-page {
    grid-template-columns: 1fr;
    height: auto;
  }

  .ai-session-sidebar {
    min-height: 220px;
  }

  .ai-task-preview-popover {
    left: 18px;
    right: 18px;
    width: auto;
  }
}

@media (max-width: 768px) {
  .ai-chat-surface {
    min-height: 72vh;
    padding: 18px 16px 22px;
  }

  .ai-composer-main {
    align-items: stretch;
  }

  .ai-composer-actions {
    padding-left: 0;
  }

  .ai-task-preview-grid {
    grid-template-columns: 1fr;
  }

  .ai-message-bubble {
    max-width: calc(100% - 52px);
  }
}
</style>
