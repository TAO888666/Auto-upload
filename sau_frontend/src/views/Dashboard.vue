<template>
  <div class="dashboard">
    <div v-if="false" class="page-header dashboard-header">
      <div>
        <h1>TaoX运营发布</h1>
        <p>账号、平台与素材的实时运营概览</p>
      </div>
    </div>

    <div class="dashboard-content">
      <el-row :gutter="20" class="stat-grid">
        <el-col :span="8" :xs="24" :md="8">
          <el-card class="stat-card stat-card--account">
            <div class="stat-label">账号总数</div>
            <div class="stat-value">{{ accountStats.total }}</div>
            <div class="stat-detail">正常 {{ accountStats.normal }} · 异常 {{ accountStats.abnormal }}</div>
          </el-card>
        </el-col>

        <el-col :span="8" :xs="24" :md="8">
          <el-card class="stat-card stat-card--platform">
            <div class="stat-label">已接入平台</div>
            <div class="stat-value">{{ platformStats.total }}</div>
            <div class="stat-detail">
              快手 {{ platformStats.kuaishou }} · 抖音 {{ platformStats.douyin }} · 视频号 {{ platformStats.channels }} · 小红书 {{ platformStats.xiaohongshu }}
            </div>
          </el-card>
        </el-col>

        <el-col :span="8" :xs="24" :md="8">
          <el-card class="stat-card stat-card--material">
            <div class="stat-label">素材总数</div>
            <div class="stat-value">{{ contentStats.total }}</div>
            <div class="stat-detail">视频 {{ contentStats.videos }} · 图片 {{ contentStats.images }} · 其他 {{ contentStats.others }}</div>
          </el-card>
        </el-col>
      </el-row>

      <section class="quick-actions">
        <h2>快捷操作</h2>
        <el-row :gutter="18">
          <el-col :span="6" :xs="24" :sm="12" :lg="6">
            <el-card class="action-card" @click="navigateTo('/account-management')">
              <div class="action-icon account"><el-icon><UserFilled /></el-icon></div>
              <div>
                <div class="action-title">账号管理</div>
                <div class="action-desc">管理所有平台账号</div>
              </div>
              <el-button size="small">进入账号</el-button>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="24" :sm="12" :lg="6">
            <el-card class="action-card" @click="navigateTo('/material-management')">
              <div class="action-icon material"><el-icon><Upload /></el-icon></div>
              <div>
                <div class="action-title">素材管理</div>
                <div class="action-desc">上传和管理视频素材</div>
              </div>
              <el-button size="small">进入素材</el-button>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="24" :sm="12" :lg="6">
            <el-card class="action-card" @click="navigateTo('/publish-center')">
              <div class="action-icon publish"><el-icon><Timer /></el-icon></div>
              <div>
                <div class="action-title">发布中心</div>
                <div class="action-desc">发布内容到各平台</div>
              </div>
              <el-button type="primary" size="small">开始发布</el-button>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="24" :sm="12" :lg="6">
            <el-card class="action-card" @click="navigateTo('/about')">
              <div class="action-icon about"><el-icon><DataAnalysis /></el-icon></div>
              <div>
                <div class="action-title">关于系统</div>
                <div class="action-desc">查看系统信息</div>
              </div>
              <el-button size="small">查看配置</el-button>
            </el-card>
          </el-col>
        </el-row>
      </section>

      <el-row :gutter="20" class="dashboard-bottom">
        <el-col :span="16" :xs="24" :lg="16">
          <section class="recent-materials">
            <div class="section-header">
              <h2>最近上传素材</h2>
              <el-button text @click="navigateTo('/material-management')">查看全部</el-button>
            </div>

            <el-table :data="recentMaterials" style="width: 100%" v-loading="loading">
              <el-table-column prop="filename" label="文件名" min-width="260" />
              <el-table-column prop="filesize" label="文件大小" width="120">
                <template #default="scope">
                  {{ scope.row.filesize }} MB
                </template>
              </el-table-column>
              <el-table-column prop="upload_time" label="上传时间" width="180" />
              <el-table-column label="类型" width="100">
                <template #default="scope">
                  <el-tag :type="getFileTypeTag(scope.row.filename)" effect="plain" size="small">
                    {{ getFileType(scope.row.filename) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="!loading && recentMaterials.length === 0" description="暂无素材数据" />
          </section>
        </el-col>

        <el-col :span="8" :xs="24" :lg="8">
          <section class="operation-overview">
            <h2>运营概览</h2>
            <div class="overview-row">
              <span>账号健康</span>
              <strong>{{ accountStats.normal }} / {{ accountStats.total }}</strong>
              <div class="overview-track">
                <i :style="{ width: `${accountHealthPercent}%` }" />
              </div>
            </div>
            <div class="overview-row">
              <span>素材可用</span>
              <strong>{{ contentStats.total }}</strong>
              <div class="overview-track">
                <i class="blue" :style="{ width: `${materialPercent}%` }" />
              </div>
            </div>
            <div class="overview-row">
              <span>平台覆盖</span>
              <strong>{{ platformStats.total }} 个平台</strong>
              <div class="overview-track">
                <i class="violet" :style="{ width: `${platformPercent}%` }" />
              </div>
            </div>
          </section>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { UserFilled, Upload, Timer, DataAnalysis } from '@element-plus/icons-vue'
import { accountApi } from '@/api/account'
import { materialApi } from '@/api/material'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const accountStore = useAccountStore()
const appStore = useAppStore()
const loading = ref(false)

const accountStats = computed(() => {
  const accounts = accountStore.accounts
  const normal = accounts.filter(account => account.status === '正常').length
  const abnormal = accounts.filter(account => account.status !== '正常' && account.status !== '验证中').length
  return { total: accounts.length, normal, abnormal }
})

const platformStats = computed(() => {
  const accounts = accountStore.accounts
  const kuaishou = accounts.filter(account => account.platform === '快手').length
  const douyin = accounts.filter(account => account.platform === '抖音').length
  const channels = accounts.filter(account => account.platform === '视频号').length
  const xiaohongshu = accounts.filter(account => account.platform === '小红书').length
  const total = [kuaishou, douyin, channels, xiaohongshu].filter(count => count > 0).length
  return { total, kuaishou, douyin, channels, xiaohongshu }
})

const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

const contentStats = computed(() => {
  const materials = appStore.materials
  const videos = materials.filter(material => videoExtensions.some(ext => material.filename.toLowerCase().endsWith(ext))).length
  const images = materials.filter(material => imageExtensions.some(ext => material.filename.toLowerCase().endsWith(ext))).length
  return { total: materials.length, videos, images, others: materials.length - videos - images }
})

const recentMaterials = computed(() => {
  return [...appStore.materials]
    .sort((left, right) => new Date(right.upload_time) - new Date(left.upload_time))
    .slice(0, 5)
})

const accountHealthPercent = computed(() => {
  if (!accountStats.value.total) return 0
  return Math.round((accountStats.value.normal / accountStats.value.total) * 100)
})

const materialPercent = computed(() => Math.min(100, Math.max(8, contentStats.value.total ? 82 : 0)))
const platformPercent = computed(() => Math.round((platformStats.value.total / 4) * 100))

const getFileType = (filename) => {
  const normalized = filename.toLowerCase()
  if (videoExtensions.some(ext => normalized.endsWith(ext))) return '视频'
  if (imageExtensions.some(ext => normalized.endsWith(ext))) return '图片'
  return '其他'
}

const getFileTypeTag = (filename) => {
  return { 视频: 'success', 图片: 'warning', 其他: 'info' }[getFileType(filename)] || 'info'
}

const navigateTo = (path) => {
  router.push(path)
}

const fetchDashboardData = async () => {
  loading.value = true
  try {
    const [accountRes, materialRes] = await Promise.allSettled([
      accountApi.getAccounts(),
      materialApi.getAllMaterials()
    ])

    if (accountRes.status === 'fulfilled' && accountRes.value.code === 200) {
      accountStore.setAccounts(accountRes.value.data)
    }
    if (materialRes.status === 'fulfilled' && materialRes.value.code === 200) {
      appStore.setMaterials(materialRes.value.data)
    }
  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.dashboard-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;

  p {
    margin: 6px 0 0;
    color: $text-secondary;
    font-size: 13px;
  }
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stat-grid {
  row-gap: 16px;
}

.stat-card {
  position: relative;
  min-height: 118px;
  overflow: hidden;

  :deep(.el-card__body) {
    height: 100%;
  }

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 18px;
    bottom: 18px;
    width: 3px;
    border-radius: 999px;
    background: $primary-color;
  }

  &--platform::before {
    background: #7c5cff;
  }

  &--material::before {
    background: $success-color;
  }
}

.stat-label {
  color: $text-secondary;
  font-size: 13px;
  font-weight: 600;
}

.stat-value {
  margin-top: 12px;
  color: $text-primary;
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}

.stat-detail {
  margin-top: 12px;
  color: $text-secondary;
  font-size: 13px;
}

.quick-actions,
.recent-materials,
.operation-overview {
  padding: 20px;
  border: 1px solid $border-light;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: $box-shadow-light;

  h2 {
    margin: 0 0 16px;
    color: $text-primary;
    font-size: 18px;
    font-weight: 800;
  }
}

.quick-actions {
  .el-row {
    row-gap: 16px;
  }
}

.action-card {
  cursor: pointer;
  min-height: 98px;

  :deep(.el-card__body) {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) auto;
    align-items: center;
    gap: 14px;
  }
}

.action-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef4ff;
  color: $primary-color;

  &.material {
    background: #eaf8f2;
    color: $success-color;
  }

  &.publish {
    background: #f3efff;
    color: #7c5cff;
  }

  &.about {
    background: #fff7e8;
    color: $warning-color;
  }
}

.action-title {
  color: $text-primary;
  font-weight: 800;
}

.action-desc {
  margin-top: 5px;
  color: $text-secondary;
  font-size: 13px;
}

.dashboard-bottom {
  row-gap: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;

  h2 {
    margin-bottom: 0;
  }
}

.operation-overview {
  min-height: 100%;
}

.overview-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 18px;
  align-items: center;
  padding: 14px 0;

  span {
    color: $text-secondary;
    font-size: 13px;
  }

  strong {
    color: $text-primary;
    font-size: 24px;
    font-weight: 800;
  }

.overview-track {
    grid-column: 1 / -1;
    display: block;
    width: 100%;
    height: 7px;
    max-width: 100%;
    border-radius: 999px;
    background: #e8eef7;
    overflow: hidden;
  }

  i {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: $success-color;
  }

  .blue {
    background: $primary-color;
  }

  .violet {
    background: #7c5cff;
  }
}
</style>
