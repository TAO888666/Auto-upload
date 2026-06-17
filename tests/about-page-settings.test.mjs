import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viewPath = path.resolve('sau_frontend/src/views/About.vue')
const apiPath = path.resolve('sau_frontend/src/api/aiPublish.js')

const viewExists = fs.existsSync(viewPath)
const viewSource = viewExists ? fs.readFileSync(viewPath, 'utf8') : ''
const apiSource = fs.readFileSync(apiPath, 'utf8')

test('about page uses the same admin container language as account and material pages', () => {
  assert.equal(viewExists, true)
  assert.equal(viewSource.includes("import { aiPublishApi } from '@/api/aiPublish'"), true)
  assert.equal(viewSource.includes('loadAiPublishConfig'), true)
  assert.equal(viewSource.includes('saveAiPublishConfig'), true)
  assert.equal(viewSource.includes('testAiPublishConfig'), true)
  assert.equal(viewSource.includes('loadStorageUsage'), true)
  assert.equal(viewSource.includes('clearStorageTarget'), true)
  assert.equal(viewSource.includes('AI对话附件清理'), true)
  assert.equal(viewSource.includes('作品文件清理'), true)
  assert.equal(viewSource.includes('页面说明'), true)
  assert.equal(viewSource.includes('ElMessageBox.confirm'), true)

  assert.equal(viewSource.includes('class="page-header"'), true)
  assert.equal(viewSource.includes('class="about-container"'), true)
  assert.equal(viewSource.includes('class="about-grid"'), true)
  assert.equal(viewSource.includes('class="about-panel about-settings-panel"'), true)
  assert.equal(viewSource.includes('class="about-panel about-storage-panel"'), true)
  assert.equal(viewSource.includes('class="about-panel about-info-panel"'), true)
  assert.equal(viewSource.includes('class="about-storage-list"'), true)
  assert.equal(viewSource.includes('class="about-storage-card"'), true)
  assert.equal(viewSource.includes('class="about-link-showcase"'), true)
  assert.equal(viewSource.includes('class="card creator-card"'), true)
  assert.equal(viewSource.includes('/about-card-avatar.png'), true)
  assert.equal(viewSource.includes('https://v.douyin.com/HI8Xn395Wic/'), true)
  assert.equal(viewSource.includes('https://www.taoxai.top/'), true)
  assert.equal(viewSource.includes('抖音主页'), true)
  assert.equal(viewSource.includes('更多工具'), true)

  assert.equal(viewSource.includes('radial-gradient('), true)
  assert.equal(viewSource.includes('.card__avatar'), true)
  assert.equal(viewSource.includes('.card__btn-solid'), true)
  assert.equal(viewSource.includes('#faf5ee'), false)
  assert.equal(viewSource.includes('#f97316'), false)
  assert.equal(viewSource.includes('about-top-row'), false)
})

test('ai publish api exposes storage usage and cleanup methods', () => {
  assert.equal(apiSource.includes('loadStorageUsage()'), true)
  assert.equal(apiSource.includes("return http.get('/aiPublish/storage')"), true)
  assert.equal(apiSource.includes('clearStorageTarget(target)'), true)
  assert.equal(apiSource.includes("return http.post('/aiPublish/storage/cleanup', { target })"), true)
})
