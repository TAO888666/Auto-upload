import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const taskProgressViewPath = path.resolve('sau_frontend/src/views/TaskProgress.vue')
const source = fs.readFileSync(taskProgressViewPath, 'utf8')

test('task progress view renders SSE-driven publish cards grouped by platform', () => {
  assert.equal(source.includes('EventSource(taskProgressApi.getPublishTaskStreamUrl(taskId))'), true)
  assert.equal(source.includes('filters'), true)
  assert.equal(source.includes('line-progress'), true)
  assert.equal(source.includes('发布中'), true)
  assert.equal(source.includes('全部成功'), true)
  assert.equal(source.includes('上传失败'), true)
})

test('task progress view fetches the current publish task snapshot before opening SSE', () => {
  assert.equal(source.includes('taskProgressApi.getCurrentPublishTask()'), true)
  assert.equal(source.includes("eventSource.addEventListener('task-snapshot'"), true)
  assert.equal(source.includes('overallProgress'), true)
})

test('task progress view supports pause, clear, search, failed filter, and retry actions', () => {
  assert.equal(source.includes('暂停发布任务'), true)
  assert.equal(source.includes('清除当前任务卡片信息'), true)
  assert.equal(source.includes('失败任务'), true)
  assert.equal(source.includes('搜索账号 / 视频标题 / 平台'), true)
  assert.equal(source.includes('retryFailedItem(item)'), true)
})

test('task progress view preserves other failed cards when retrying one item', () => {
  assert.equal(source.includes('const retainedFailedItems = ref([])'), true)
  assert.equal(source.includes('const getRemainingFailedItemsForTask = (taskId, excludedItemId) => {'), true)
  assert.equal(source.includes('const response = await taskProgressApi.retryPublishTaskItem(item.taskId, item.itemId)'), true)
  assert.equal(source.includes(':disabled="!item.taskId || isRetrying(item.itemId)"'), true)
})

test('task progress view hides generated uuid prefixes in displayed media titles', () => {
  assert.equal(source.includes('const formatTaskVideoTitle = (videoTitle) => {'), true)
  assert.equal(source.includes('UUID_PREFIX_PATTERN'), true)
  assert.equal(source.includes(':title="formatTaskVideoTitle(item.videoTitle)"'), true)
  assert.equal(source.includes('{{ formatTaskVideoTitle(item.videoTitle) }}'), true)
})

test('task progress view uses compact spacing so publish cards sit higher', () => {
  assert.equal(source.includes('gap: 10px;'), true)
  assert.equal(source.includes('padding: 8px 14px;'), true)
  assert.equal(source.includes('padding: 14px;'), true)
  assert.equal(source.includes('gap: 14px;'), true)
  assert.equal(source.includes('margin-top: 14px;'), true)
})
