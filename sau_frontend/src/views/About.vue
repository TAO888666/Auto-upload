<template>
  <div class="about-page">
    <div class="page-header">
      <h1>关于</h1>
    </div>

    <div class="about-container">
      <div class="about-grid">
        <section class="about-panel about-settings-panel">
          <h2 class="section-title">AI 接入设置</h2>

          <form class="about-form" @submit.prevent="saveAiPublishConfig">
            <div class="about-form-grid">
              <div class="about-form-item">
                <label class="about-form-label">提供商</label>
                <el-select v-model="aiConfigForm.provider" placeholder="请选择提供商">
                  <el-option label="DeepSeek" value="deepseek" />
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Gemini" value="gemini" />
                  <el-option label="Qwen" value="qwen" />
                  <el-option label="火山方舟 / 豆包" value="ark" />
                  <el-option label="Custom" value="custom" />
                </el-select>
              </div>

              <div class="about-form-item">
                <label class="about-form-label">默认模型</label>
                <el-input
                  v-model="aiConfigForm.defaultModel"
                  placeholder="例如：deepseek-chat"
                />
              </div>

              <div class="about-form-item about-form-item-full">
                <label class="about-form-label">API Base URL</label>
                <el-input
                  v-model="aiConfigForm.apiBase"
                  placeholder="https://api.deepseek.com/v1"
                />
              </div>

              <div class="about-form-item about-form-item-full">
                <label class="about-form-label">API Key</label>
                <el-input
                  v-model="aiConfigForm.apiKey"
                  type="password"
                  show-password
                  placeholder="请输入 API Key"
                />
              </div>
            </div>

            <div class="about-form-note">配置完成后可直接回 AI 发布使用</div>

            <div class="about-action-row">
              <el-button :loading="testingAiConfig" @click="testAiPublishConfig">
                测试连接
              </el-button>
              <el-button type="primary" :loading="savingAiConfig" native-type="submit">
                保存配置
              </el-button>
            </div>
          </form>
        </section>

        <section class="about-panel about-storage-panel">
          <h2 class="section-title">存储清理</h2>

          <div class="about-storage-list">
            <article class="about-storage-card">
              <div class="about-storage-head">
                <h3>AI对话附件清理</h3>
                <span>{{ formatUsageCount(storageUsage.aiAttachments) }}</span>
              </div>

              <strong class="about-storage-size">
                {{ formatUsageSize(storageUsage.aiAttachments) }}
              </strong>

              <el-button
                type="primary"
                class="about-storage-btn"
                :loading="cleaningTarget === 'aiAttachments'"
                @click="clearStorageTarget('aiAttachments')"
              >
                立即清理
              </el-button>
            </article>

            <article class="about-storage-card">
              <div class="about-storage-head">
                <h3>作品文件清理</h3>
                <span>{{ formatUsageCount(storageUsage.workFiles) }}</span>
              </div>

              <strong class="about-storage-size">
                {{ formatUsageSize(storageUsage.workFiles) }}
              </strong>

              <el-button
                type="primary"
                class="about-storage-btn"
                :loading="cleaningTarget === 'workFiles'"
                @click="clearStorageTarget('workFiles')"
              >
                立即清理
              </el-button>
            </article>
          </div>
        </section>

        <section class="about-panel about-info-panel">
          <h2 class="section-title">页面说明</h2>

          <div class="about-link-showcase">
            <article class="card creator-card">
              <div class="card__img" aria-hidden="true" />
              <div class="card__avatar">
                <img src="/about-card-avatar.png" alt="欧哥头像">
              </div>
              <div class="card__title">欧哥</div>
              <div class="card__subtitle">AI工具导航 · 欧哥流量计划</div>
              <div class="card__actions">
                <a
                  class="card__btn card__btn-solid"
                  href="https://v.douyin.com/HI8Xn395Wic/"
                  target="_blank"
                  rel="noreferrer"
                >
                  抖音主页
                </a>
                <a
                  class="card__btn"
                  href="https://www.taoxai.top/"
                  target="_blank"
                  rel="noreferrer"
                >
                  更多工具
                </a>
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiPublishApi } from '@/api/aiPublish'

const aiConfigForm = reactive({
  provider: 'deepseek',
  apiBase: 'https://api.deepseek.com/v1',
  apiKey: '',
  defaultModel: 'deepseek-chat',
})

const savingAiConfig = ref(false)
const testingAiConfig = ref(false)
const cleaningTarget = ref('')
const storageUsage = reactive({
  aiAttachments: {
    sizeLabel: '0 B',
    fileCount: 0,
    dirCount: 0,
  },
  workFiles: {
    sizeLabel: '0 B',
    fileCount: 0,
    dirCount: 0,
  },
})

const loadAiPublishConfig = async () => {
  try {
    const response = await aiPublishApi.loadConfig()
    aiConfigForm.provider = response.data.provider || 'deepseek'
    aiConfigForm.apiBase = response.data.apiBase || 'https://api.deepseek.com/v1'
    aiConfigForm.apiKey = ''
    aiConfigForm.defaultModel = response.data.defaultModel || 'deepseek-chat'
  } catch (error) {
    console.error('load ai publish config failed:', error)
    ElMessage.error(error?.message || '加载 AI 配置失败')
  }
}

const saveAiPublishConfig = async () => {
  savingAiConfig.value = true
  try {
    await aiPublishApi.saveConfig({
      provider: aiConfigForm.provider,
      apiBase: aiConfigForm.apiBase,
      apiKey: aiConfigForm.apiKey,
      defaultModel: aiConfigForm.defaultModel,
    })
    ElMessage.success('AI 配置已保存')
  } catch (error) {
    console.error('save ai publish config failed:', error)
    ElMessage.error(error?.message || '保存 AI 配置失败')
  } finally {
    savingAiConfig.value = false
  }
}

const testAiPublishConfig = async () => {
  testingAiConfig.value = true
  try {
    const response = await aiPublishApi.testConfig({
      provider: aiConfigForm.provider,
      apiBase: aiConfigForm.apiBase,
      apiKey: aiConfigForm.apiKey,
      defaultModel: aiConfigForm.defaultModel,
    })
    ElMessage.success(response.data?.message || '测试连接成功')
  } catch (error) {
    console.error('test ai publish config failed:', error)
    ElMessage.error(error?.message || '测试连接失败')
  } finally {
    testingAiConfig.value = false
  }
}

const loadStorageUsage = async () => {
  try {
    const response = await aiPublishApi.loadStorageUsage()
    storageUsage.aiAttachments = response.data?.aiAttachments || storageUsage.aiAttachments
    storageUsage.workFiles = response.data?.workFiles || storageUsage.workFiles
  } catch (error) {
    console.error('load storage usage failed:', error)
    ElMessage.error(error?.message || '加载存储占用失败')
  }
}

const clearStorageTarget = async (target) => {
  const title = target === 'aiAttachments' ? 'AI对话附件清理' : '作品文件清理'
  const message = target === 'aiAttachments'
    ? '将清理 tmp/ai_publish_uploads 中的全部临时附件，确认继续吗？'
    : '将清空 videoFile 目录中的全部作品文件，确认继续吗？'

  await ElMessageBox.confirm(message, title, {
    type: 'warning',
    confirmButtonText: '确认清理',
    cancelButtonText: '取消',
  })

  cleaningTarget.value = target
  try {
    const response = await aiPublishApi.clearStorageTarget(target)
    const current = response.data?.current
    if (target === 'aiAttachments' && current) {
      storageUsage.aiAttachments = current
    }
    if (target === 'workFiles' && current) {
      storageUsage.workFiles = current
    }
    ElMessage.success(response.data?.message || '清理完成')
    await loadStorageUsage()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('clear storage target failed:', error)
      ElMessage.error(error?.message || '清理失败')
    }
  } finally {
    cleaningTarget.value = ''
  }
}

const formatUsageSize = (payload) => payload?.sizeLabel || '0 B'

const formatUsageCount = (payload) => {
  const fileCount = Number(payload?.fileCount || 0)
  const dirCount = Number(payload?.dirCount || 0)
  return `${fileCount} 个文件 / ${dirCount} 个目录`
}

onMounted(async () => {
  await Promise.all([loadAiPublishConfig(), loadStorageUsage()])
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.about-page {
  .page-header {
    margin-bottom: 20px;

    h1 {
      margin: 0;
      font-size: 30px;
      font-weight: 800;
      color: $text-primary;
    }
  }

  .about-container {
    background: transparent;
    border-radius: 0;
    box-shadow: none;
    padding: 0;
  }

  .about-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
    gap: 20px;
    align-items: start;
  }

  .about-panel {
    min-width: 0;
    padding: 24px;
    border: 1px solid #e3e8f0;
    border-radius: 14px;
    background: #fff;
    box-shadow: 0 8px 20px rgba(21, 32, 51, 0.05);
  }

  .about-info-panel {
    grid-column: 1 / -1;
  }

  .about-link-showcase {
    display: flex;
    justify-content: center;
    padding: 28px;
    border-radius: 24px;
    background:
      radial-gradient(circle at top, rgba(126, 87, 255, 0.24), transparent 42%),
      linear-gradient(180deg, #1b1624 0%, #110f18 100%);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }

  .section-title {
    margin: 0 0 20px;
    font-size: 18px;
    font-weight: 800;
    color: $text-primary;
  }

  .about-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .about-form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  .about-form-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }

  .about-form-item-full {
    grid-column: 1 / -1;
  }

  .about-form-label {
    font-size: 14px;
    color: #606266;
  }

  .about-form-note {
    font-size: 12px;
    color: #909399;
  }

  .about-action-row {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .about-storage-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .about-storage-card {
    border: 1px solid #e3e8f0;
    border-radius: 10px;
    background: #f8fafd;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .about-storage-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
      color: #111827;
    }

    span {
      font-size: 12px;
      color: #909399;
      white-space: nowrap;
    }
  }

  .about-storage-size {
    font-size: 28px;
    line-height: 1;
    color: #303133;
  }

  .about-storage-btn {
    width: 100%;
  }

  .creator-card {
    --main-color: #000;
    --submain-color: #78858f;
    --bg-color: #fff;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    position: relative;
    width: 300px;
    height: 384px;
    display: flex;
    flex-direction: column;
    align-items: center;
    border-radius: 20px;
    background: var(--bg-color);
    box-shadow: 0 22px 48px rgba(0, 0, 0, 0.28);
    overflow: hidden;
  }

  .card__img {
    height: 192px;
    width: 100%;
    border-radius: 20px 20px 0 0;
    background:
      linear-gradient(135deg, rgba(255, 255, 255, 0.14) 25%, transparent 25%) -24px 0 / 48px 48px,
      linear-gradient(225deg, rgba(255, 255, 255, 0.14) 25%, transparent 25%) -24px 0 / 48px 48px,
      linear-gradient(315deg, rgba(255, 255, 255, 0.14) 25%, transparent 25%) 0 0 / 48px 48px,
      linear-gradient(45deg, rgba(255, 255, 255, 0.14) 25%, transparent 25%) 0 0 / 48px 48px,
      linear-gradient(180deg, #af93ff 0%, #8566f3 100%);
  }

  .card__avatar {
    position: absolute;
    width: 114px;
    height: 114px;
    background: var(--bg-color);
    border-radius: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    top: calc(50% - 57px);
    box-shadow: 0 12px 30px rgba(10, 10, 20, 0.28);

    img {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      object-fit: cover;
      object-position: center top;
      display: block;
    }
  }

  .card__title {
    margin-top: 60px;
    font-weight: 700;
    font-size: 18px;
    color: var(--main-color);
  }

  .card__subtitle {
    margin-top: 10px;
    padding: 0 20px;
    text-align: center;
    font-weight: 400;
    font-size: 15px;
    color: var(--submain-color);
  }

  .card__actions {
    margin-top: 15px;
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: center;
  }

  .card__btn {
    width: 76px;
    height: 31px;
    border: 2px solid var(--main-color);
    border-radius: 4px;
    font-weight: 700;
    font-size: 11px;
    color: var(--main-color);
    background: var(--bg-color);
    text-transform: uppercase;
    transition: all 0.3s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
  }

  .card__btn-solid {
    background: var(--main-color);
    color: var(--bg-color);
  }

  .card__btn:hover {
    background: var(--main-color);
    color: var(--bg-color);
  }

  .card__btn-solid:hover {
    background: var(--bg-color);
    color: var(--main-color);
  }

  @media (max-width: 1200px) {
    .about-grid {
      grid-template-columns: 1fr;
    }

    .about-info-panel {
      grid-column: auto;
    }
  }

  @media (max-width: 900px) {
    .about-form-grid {
      grid-template-columns: 1fr;
    }

    .about-action-row {
      flex-direction: column;
    }

    .about-link-showcase {
      padding: 20px 12px;
    }

    .creator-card {
      width: min(300px, 100%);
    }
  }
}
</style>
