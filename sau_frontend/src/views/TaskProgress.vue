<template>
  <div class="task-progress-page">
    <div class="progress-shell">
      <header class="page-header task-header">
        <div v-if="false" class="page-header__main">
          <p class="page-kicker">实时发布看板</p>
          <div class="page-title-row">
            <h1>任务进度</h1>
            <span class="connection-badge" :class="connectionState">
              {{ connectionText }}
            </span>
          </div>
          <p class="page-subtitle">
            {{ task ? taskStatusText : '当前还没有发布任务，创建任务后这里会实时显示卡片进度。' }}
          </p>
        </div>

        <div class="header-actions">
          <el-button type="warning" plain :disabled="!canPauseTask" @click="pauseCurrentTask">
            暂停发布任务
          </el-button>
          <el-button plain :disabled="!canClearTask" @click="clearCurrentTask">
            清除当前任务卡片信息
          </el-button>
        </div>
      </header>

      <section v-if="task" class="overview-panel">
        <div class="overview-stats">
          <div v-for="stat in summaryCards" :key="stat.label" class="stat-card">
            <span class="stat-label">{{ stat.label }}</span>
            <strong class="stat-value">{{ stat.value }}</strong>
          </div>
        </div>

        <div class="overall-progress">
          <div class="overall-progress__meta">
            <span>整体进度</span>
            <span>{{ overallProgress }}%</span>
          </div>
          <div class="overall-progress__track">
            <span class="overall-progress__fill" :style="{ width: `${overallProgress}%` }" />
          </div>
        </div>
      </section>

      <section class="toolbar-panel">
        <div class="filter-pills">
          <button
            v-for="filter in filters"
            :key="filter.key"
            type="button"
            class="filter-pill"
            :class="{ active: activeFilter === filter.key }"
            @click="activeFilter = filter.key"
          >
            {{ filter.label }}
          </button>
        </div>

        <label class="search-field">
          <span class="search-icon">⌕</span>
          <input
            v-model.trim="searchKeyword"
            type="text"
            placeholder="搜索账号 / 视频标题 / 平台"
          >
        </label>
      </section>

      <section class="cards-panel">
        <div v-if="filteredItems.length" class="item-grid">
          <article
            v-for="item in filteredItems"
            :key="`${item.taskId || 'task'}-${item.itemId}`"
            class="publish-item-card"
            :class="item.status"
          >
            <div class="publish-item-card__top">
              <span class="platform-pill" :class="item.platform">
                {{ getPlatformLabel(item.platform) }}
              </span>
              <span class="account-handle">@{{ item.accountName || '未命名账号' }}</span>
            </div>

            <h3 class="video-title" :title="formatTaskVideoTitle(item.videoTitle)">
              {{ formatTaskVideoTitle(item.videoTitle) }}
            </h3>

            <div class="status-row">
              <div class="status-copy">
                <span class="status-step">{{ getItemStatusLabel(item.status) }}</span>
                <span v-if="item.status === 'error' && item.errorMessage" class="status-reason">
                  {{ item.errorMessage }}
                </span>
                <span v-else-if="item.message" class="status-reason muted">
                  {{ item.message }}
                </span>
              </div>
              <span class="status-percent">{{ item.progress }}%</span>
            </div>

            <div class="line-progress" :class="item.status">
              <span class="line-progress__fill" :style="{ width: `${item.progress}%` }" />
            </div>

            <div class="card-footer">
              <div class="footer-meta">
                <span>{{ getPlatformLabel(item.platform) }}</span>
                <span>{{ item.accountName || '未命名账号' }}</span>
              </div>

              <el-button
                v-if="item.status === 'error'"
                size="small"
                type="danger"
                plain
                :disabled="!item.taskId || isRetrying(item.itemId)"
                :loading="isRetrying(item.itemId)"
                @click="retryFailedItem(item)"
              >
                重试
              </el-button>
            </div>
          </article>
        </div>

        <el-empty v-else description="当前筛选条件下没有任务卡片" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskProgressApi } from '@/api/taskProgress'

const PLATFORM_META = {
  all: { label: '全部' },
  douyin: { label: '抖音' },
  kuaishou: { label: '快手' },
  xiaohongshu: { label: '小红书' },
  weixin: { label: '视频号' },
  failed: { label: '失败任务' },
}

const filters = [
  { key: 'all', label: '全部' },
  { key: 'douyin', label: '抖音' },
  { key: 'kuaishou', label: '快手' },
  { key: 'xiaohongshu', label: '小红书' },
  { key: 'weixin', label: '视频号' },
  { key: 'failed', label: '失败任务' },
]

const task = ref(null)
const loading = ref(false)
const connectionState = ref('idle')
const activeFilter = ref('all')
const searchKeyword = ref('')
const retryingItemIds = ref([])
const retainedFailedItems = ref([])

let eventSource = null

const UUID_PREFIX_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i

const formatTaskVideoTitle = (videoTitle) => {
  return String(videoTitle || '').replace(UUID_PREFIX_PATTERN, '')
}

const connectionText = computed(() => {
  switch (connectionState.value) {
    case 'connecting':
      return 'SSE 连接中'
    case 'live':
      return 'SSE 实时中'
    case 'retrying':
      return 'SSE 重连中'
    case 'closed':
      return '已停止'
    case 'error':
      return '连接异常'
    default:
      return '未连接'
  }
})

const taskStatusText = computed(() => {
  if (!task.value) return ''

  switch (task.value.status) {
    case 'queued':
      return '任务已创建，等待发布队列启动。'
    case 'running':
      return '任务正在执行中，请查看下方每条视频卡片的状态。'
    case 'paused':
      return '任务已暂停，当前正在执行的卡片会收尾，剩余卡片不会继续启动。'
    case 'success':
      return '任务已完成。'
    case 'error':
      return task.value.message || '任务执行失败。'
    default:
      return task.value.message || '任务状态未知。'
  }
})

const overallProgress = computed(() => {
  if (!task.value?.totalItems) return 0
  return Math.round((task.value.completedItems / task.value.totalItems) * 100)
})

const summaryCards = computed(() => {
  if (!task.value) return []

  return [
    { label: '任务总数', value: task.value.totalItems || 0 },
    { label: '等待执行', value: (task.value.pendingItems || 0) + (task.value.pausedItems || 0) },
    { label: '正在发布', value: task.value.runningItems || 0 },
    { label: '发布成功', value: task.value.successItems || 0 },
    { label: '发布失败', value: task.value.errorItems || 0 },
  ]
})

const canPauseTask = computed(() => {
  return Boolean(task.value?.taskId) && ['queued', 'running'].includes(task.value?.status)
})

const canClearTask = computed(() => {
  return Boolean(task.value?.taskId) && !['queued', 'running'].includes(task.value?.status)
})

const filteredItems = computed(() => {
  const items = getVisibleTaskItems()
  const keyword = searchKeyword.value.trim().toLowerCase()

  return items
    .filter((item) => {
      if (activeFilter.value === 'failed') return item.status === 'error'
      if (activeFilter.value !== 'all') return item.platform === activeFilter.value
      return true
    })
    .filter((item) => {
      if (!keyword) return true

      const haystack = [
        item.videoTitle,
        formatTaskVideoTitle(item.videoTitle),
        item.accountName,
        getPlatformLabel(item.platform),
      ].join(' ').toLowerCase()

      return haystack.includes(keyword)
    })
    .sort((left, right) => {
      const taskTimeDelta = getTaskTimestamp(right.taskCreatedAt) - getTaskTimestamp(left.taskCreatedAt)
      if (taskTimeDelta !== 0) return taskTimeDelta
      return left.orderIndex - right.orderIndex
    })
})

const getPlatformLabel = (platform) => {
  return PLATFORM_META[platform]?.label || platform || '未知平台'
}

const getItemStatusLabel = (status) => {
  switch (status) {
    case 'running':
      return '发布中'
    case 'success':
      return '全部成功'
    case 'error':
      return '上传失败'
    case 'paused':
      return '已暂停'
    case 'skipped':
      return '未执行'
    default:
      return '等待执行'
  }
}

const normalizeTaskSnapshot = (snapshot) => {
  if (!snapshot) return null

  const items = Array.isArray(snapshot.items)
    ? snapshot.items.map(item => ({
      taskId: snapshot.taskId || '',
      taskCreatedAt: snapshot.createdAt || '',
      itemId: item.itemId,
      orderIndex: Number(item.orderIndex || 0),
      taskIndex: Number(item.taskIndex || 0),
      platform: item.platform || '',
      accountName: item.accountName || '',
      title: item.title || '',
      videoTitle: item.videoTitle || item.title || '',
      status: item.status || 'pending',
      progress: Number(item.progress || 0),
      message: item.message || '',
      errorMessage: item.errorMessage || '',
    }))
    : []

  return { ...snapshot, items }
}

const getTaskTimestamp = (value) => {
  const parsed = Date.parse(value || '')
  return Number.isNaN(parsed) ? 0 : parsed
}

const dedupeTaskItems = (items) => {
  const itemMap = new Map()

  items.forEach((item) => {
    if (!item?.itemId) return
    itemMap.set(`${item.taskId || ''}:${item.itemId}`, item)
  })

  return Array.from(itemMap.values())
}

const getVisibleTaskItems = () => {
  const currentItems = Array.isArray(task.value?.items) ? task.value.items : []
  return dedupeTaskItems([...currentItems, ...retainedFailedItems.value])
}

const getRemainingFailedItemsForTask = (taskId, excludedItemId) => {
  return getVisibleTaskItems().filter((candidate) => {
    return candidate.taskId === taskId && candidate.status === 'error' && candidate.itemId !== excludedItemId
  })
}

const closeTaskStream = () => {
  if (!eventSource) return
  eventSource.close()
  eventSource = null
}

const applyTaskSnapshot = (snapshot) => {
  task.value = normalizeTaskSnapshot(snapshot)
  if (['success', 'error', 'paused'].includes(task.value?.status)) {
    connectionState.value = 'closed'
    closeTaskStream()
  }
}

const connectTaskStream = (taskId) => {
  if (!taskId) return

  closeTaskStream()
  connectionState.value = 'connecting'

  eventSource = new EventSource(taskProgressApi.getPublishTaskStreamUrl(taskId))
  eventSource.onopen = () => {
    connectionState.value = 'live'
  }

  eventSource.addEventListener('task-snapshot', (event) => {
    try {
      const snapshot = JSON.parse(event.data)
      applyTaskSnapshot(snapshot)
      if (['success', 'error', 'paused'].includes(snapshot?.status)) {
        connectionState.value = 'closed'
        closeTaskStream()
      }
    } catch (error) {
      console.error('failed to parse publish task snapshot:', error)
    }
  })

  eventSource.addEventListener('task-error', (event) => {
    connectionState.value = 'error'
    try {
      const payload = JSON.parse(event.data)
      ElMessage.error(payload?.message || '任务进度连接失败')
    } catch (error) {
      ElMessage.error('任务进度连接失败')
    }
    closeTaskStream()
  })

  eventSource.onerror = () => {
    if (['success', 'error', 'paused'].includes(task.value?.status)) {
      connectionState.value = 'closed'
      closeTaskStream()
      return
    }
    connectionState.value = 'retrying'
  }
}

const loadCurrentTask = async () => {
  loading.value = true
  try {
    const response = await taskProgressApi.getCurrentPublishTask()
    applyTaskSnapshot(response.data)

    if (response.data?.taskId && ['queued', 'running'].includes(response.data.status)) {
      connectTaskStream(response.data.taskId)
    } else if (!response.data) {
      closeTaskStream()
      connectionState.value = 'idle'
    }
  } catch (error) {
    console.error('load current publish task failed:', error)
    connectionState.value = 'error'
  } finally {
    loading.value = false
  }
}

const pauseCurrentTask = async () => {
  if (!task.value?.taskId) return

  try {
    await taskProgressApi.pausePublishTask(task.value.taskId)
    ElMessage.success('已请求暂停，当前正在执行的卡片会收尾，后续卡片不会继续启动。')
  } catch (error) {
    console.error('pause publish task failed:', error)
  }
}

const clearCurrentTask = async () => {
  if (!task.value?.taskId) return

  try {
    await ElMessageBox.confirm(
      '清除后当前任务卡片信息会从看板移除，确定继续吗？',
      '清除当前任务卡片信息',
      {
        type: 'warning',
        confirmButtonText: '清除',
        cancelButtonText: '取消',
      },
    )
  } catch (error) {
    return
  }

  try {
    await taskProgressApi.clearPublishTask(task.value.taskId)
    closeTaskStream()
    task.value = null
    retainedFailedItems.value = []
    connectionState.value = 'idle'
    ElMessage.success('当前任务卡片信息已清除。')
  } catch (error) {
    console.error('clear publish task failed:', error)
  }
}

const isRetrying = (itemId) => retryingItemIds.value.includes(itemId)

const retryFailedItem = async (item) => {
  if (!item.taskId || isRetrying(item.itemId)) return

  retryingItemIds.value = [...retryingItemIds.value, item.itemId]
  try {
    retainedFailedItems.value = dedupeTaskItems([
      ...retainedFailedItems.value.filter(candidate => !(candidate.taskId === item.taskId && candidate.itemId === item.itemId)),
      ...getRemainingFailedItemsForTask(item.taskId, item.itemId),
    ])

    const response = await taskProgressApi.retryPublishTaskItem(item.taskId, item.itemId)
    const nextTask = response.data || null
    if (nextTask?.taskId) {
      applyTaskSnapshot(nextTask)
      if (['queued', 'running'].includes(nextTask.status)) {
        connectTaskStream(nextTask.taskId)
      }
    }
    ElMessage.success('失败任务已创建重试队列。')
  } catch (error) {
    retainedFailedItems.value = dedupeTaskItems([
      ...retainedFailedItems.value,
      item,
    ])
    console.error('retry failed publish item failed:', error)
  } finally {
    retryingItemIds.value = retryingItemIds.value.filter(id => id !== item.itemId)
  }
}

onMounted(() => {
  void loadCurrentTask()
})

onBeforeUnmount(() => {
  closeTaskStream()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.task-progress-page {
  min-height: calc(100vh - 48px);
}

.progress-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-header,
.overview-panel,
.toolbar-panel,
.cards-panel {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid $border-light;
  border-radius: 12px;
  box-shadow: $box-shadow-light;
}

.task-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
  margin-bottom: 0 !important;
  padding: 0;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}

.page-kicker {
  margin: 0 0 6px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.page-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title-row h1 {
  margin: 0;
  color: $text-primary;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
}

.page-subtitle {
  margin: 6px 0 0;
  color: $text-secondary;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.connection-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 92px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: #e8eef7;
  color: #5e7088;

  &.connecting,
  &.retrying {
    background: rgba(47, 109, 246, 0.12);
    color: $primary-color;
  }

  &.live {
    background: rgba(34, 183, 122, 0.14);
    color: $success-color;
  }

  &.closed {
    background: rgba(148, 163, 184, 0.18);
    color: #475569;
  }

  &.error {
    background: rgba(239, 68, 68, 0.14);
    color: $danger-color;
  }
}

.overview-panel {
  padding: 14px 16px 16px;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.stat-card {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f8fbff;
  border: 1px solid #e4ebf5;
}

.stat-label {
  display: block;
  color: $text-secondary;
  font-size: 12px;
  margin-bottom: 6px;
}

.stat-value {
  color: $text-primary;
  font-size: 24px;
  font-weight: 800;
}

.overall-progress {
  margin-top: 14px;
}

.overall-progress__meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 7px;
  color: $text-regular;
  font-size: 13px;
  font-weight: 700;
}

.overall-progress__track {
  height: 8px;
  border-radius: 999px;
  background: #e8eef7;
  overflow: hidden;
}

.overall-progress__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, $primary-color 0%, $success-color 100%);
  transition: width 0.3s ease;
}

.toolbar-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  flex-wrap: wrap;
}

.filter-pills {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-pill {
  border: 1px solid #dce5f2;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  color: #5e7088;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-pill:hover {
  color: $text-primary;
  border-color: #b9cef8;
}

.filter-pill.active {
  color: #fff;
  background: $primary-color;
  border-color: $primary-color;
  box-shadow: 0 12px 22px rgba(47, 109, 246, 0.18);
}

.search-field {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: min(340px, 100%);
  padding: 8px 14px;
  border-radius: 999px;
  background: #f8fbff;
  border: 1px solid #dce5f2;
}

.search-icon {
  color: $text-secondary;
  font-size: 14px;
}

.search-field input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: $text-primary;
  font-size: 13px;
}

.cards-panel {
  padding: 16px;
}

.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.publish-item-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #dce5f2;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.publish-item-card:hover {
  border-color: #b9cef8;
  box-shadow: 0 14px 32px rgba(47, 109, 246, 0.10);
}

.publish-item-card.error {
  border-color: rgba(239, 68, 68, 0.28);
}

.publish-item-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.platform-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;

  &.douyin {
    background: rgba(254, 44, 85, 0.12);
    color: #fe2c55;
  }

  &.kuaishou {
    background: rgba(255, 102, 0, 0.12);
    color: #ea580c;
  }

  &.xiaohongshu {
    background: rgba(255, 36, 66, 0.12);
    color: #ff2442;
  }

  &.weixin {
    background: rgba(34, 183, 122, 0.14);
    color: $success-color;
  }
}

.account-handle,
.footer-meta {
  color: $text-secondary;
  font-size: 12px;
}

.video-title {
  margin: 0;
  color: $text-primary;
  font-size: 16px;
  line-height: 1.45;
  word-break: break-word;
}

.status-row,
.card-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.status-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.status-step {
  color: $text-primary;
  font-size: 13px;
  font-weight: 700;
}

.status-reason {
  color: $danger-color;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.status-reason.muted,
.status-percent {
  color: $text-secondary;
}

.status-percent {
  font-size: 12px;
  font-weight: 700;
}

.line-progress {
  position: relative;
  height: 7px;
  border-radius: 999px;
  background: #e8eef7;
  overflow: hidden;
}

.line-progress__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, $primary-color 0%, #38bdf8 100%);
  transition: width 0.24s ease;
}

.line-progress.running .line-progress__fill {
  background: linear-gradient(90deg, $primary-color 0%, #60a5fa 45%, $primary-color 100%);
  background-size: 160% 100%;
  animation: running-shimmer 1.1s linear infinite;
}

.line-progress.success .line-progress__fill {
  background: linear-gradient(90deg, #34d399 0%, $success-color 100%);
}

.line-progress.error .line-progress__fill {
  background: linear-gradient(90deg, #fb7185 0%, $danger-color 100%);
}

.line-progress.paused .line-progress__fill,
.line-progress.skipped .line-progress__fill {
  background: linear-gradient(90deg, #cbd5e1 0%, #94a3b8 100%);
}

.footer-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@keyframes running-shimmer {
  from {
    background-position: 0 0;
  }

  to {
    background-position: 160% 0;
  }
}

@media (max-width: 960px) {
  .task-header,
  .toolbar-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .overview-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .search-field {
    width: 100%;
    min-width: 0;
  }
}

@media (max-width: 640px) {
  .overview-stats,
  .item-grid {
    grid-template-columns: 1fr;
  }
}
</style>
