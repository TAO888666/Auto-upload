<template>
  <div class="account-management">
    <div v-if="false" class="page-header">
      <h1>账号管理</h1>
    </div>

    <div class="account-tabs">
      <div class="account-toolbar">
        <div class="account-platform-tabs">
          <button
            v-for="tab in platformTabs"
            :key="tab.name"
            type="button"
            class="account-platform-tab"
            :class="{ active: activeTab === tab.name }"
            @click="activeTab = tab.name"
          >
            {{ tab.label }}
          </button>
        </div>
        <div class="account-toolbar-actions">
          <div class="account-toolbar-search">
            <el-input
              v-model="searchKeyword"
              placeholder="输入名称或账号搜索"
              prefix-icon="Search"
              clearable
              @clear="handleSearch"
              @input="handleSearch"
            />
          </div>
          <el-button @click="handleAddGroup">新建分组</el-button>
          <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
          <el-button type="info" @click="fetchAccounts" :loading="false">
            <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
            <span v-if="appStore.isAccountRefreshing">刷新中</span>
          </el-button>
        </div>
      </div>

      <!-- 平台标签：全部、快手、抖音、视频号、小红书 -->
      <el-tabs v-model="activeTab" class="account-tabs-nav">
        <el-tab-pane
          v-for="tab in platformTabs"
          :key="tab.name"
          :label="tab.label"
          :name="tab.name"
        >
          <div class="account-list-container">
            <div v-if="false" class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button @click="handleAddGroup">新建分组</el-button>
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">刷新中</span>
                </el-button>
              </div>
            </div>

            <div class="account-group-layout">
              <aside class="group-sidebar">
                <div class="group-list">
                  <div
                    v-for="group in groupSidebarItems"
                    :key="group.id"
                    class="group-card"
                    :class="{
                      'is-active': selectedGroupId === group.id,
                      'is-system-group': group.isSystem
                    }"
                    :draggable="!group.isSystem"
                    @click="selectGroup(group.id)"
                    @dragstart="handleGroupDragStart($event, group.id)"
                    @dragover.prevent
                    @drop="handleGroupDrop($event, group.id)"
                    @dragend="handleGroupDragEnd"
                  >
                    <div class="group-card-main">
                      <template v-if="editingGroupId === group.id && !group.isSystem">
                        <el-input
                          :ref="(instance) => setGroupNameInputRef(group.id, instance)"
                          v-model="editingGroupName"
                          size="small"
                          maxlength="20"
                          @click.stop
                          @keyup.enter="commitGroupNameEdit(group.id)"
                          @keyup.esc="cancelGroupNameEdit"
                          @blur="commitGroupNameEdit(group.id)"
                        />
                      </template>
                      <template v-else>
                        <div
                          class="group-card-name-row"
                          @dblclick.stop="startEditingGroup(group.id)"
                        >
                          <span class="group-card-name">{{ group.name }}</span>
                          <span class="group-card-count">{{ getGroupAccountCount(group.id) }}</span>
                        </div>
                      </template>
                    </div>

                    <div v-if="!group.isSystem" class="group-card-actions">
                      <button
                        class="group-drag-handle"
                        type="button"
                        title="拖动调整顺序"
                        @mousedown.stop="prepareGroupDrag(group.id)"
                      >
                        <el-icon><Rank /></el-icon>
                      </button>
                      <button
                        class="group-delete-button"
                        type="button"
                        title="删除分组"
                        @click.stop="handleDeleteGroup(group.id)"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              </aside>

              <section class="group-account-panel">
                <div v-if="visibleAccounts.length > 0" class="account-list">
                  <el-table :data="visibleAccounts" row-key="id" style="width: 100%">
                    <el-table-column label="头像" width="80">
                      <template #default="scope">
                        <el-avatar :src="getAccountAvatar(scope.row)" :size="40" />
                      </template>
                    </el-table-column>
                    <el-table-column prop="name" label="名称" width="180" />
                    <el-table-column prop="platform" label="平台">
                      <template #default="scope">
                        <el-tag
                          :type="getPlatformTagType(scope.row.platform)"
                          effect="plain"
                        >
                          {{ scope.row.platform }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="分组" width="150">
                      <template #default="scope">
                        <el-tag effect="plain" type="info">
                          {{ getAccountGroupLabel(scope.row) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="status" label="状态">
                      <template #default="scope">
                        <el-tag
                          :type="getStatusTagType(scope.row.status)"
                          effect="plain"
                          :class="{ 'clickable-status': isStatusClickable(scope.row) }"
                          @click="handleStatusClick(scope.row)"
                        >
                          <el-icon :class="scope.row.isValidating ? 'is-loading' : ''" v-if="scope.row.isValidating">
                            <Loading />
                          </el-icon>
                          {{ scope.row.status }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" min-width="420">
                      <template #default="scope">
                        <div class="row-action-group">
                          <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                          <el-button
                            size="small"
                            :type="getPrimaryAccountActionType(scope.row)"
                            :loading="isPrimaryAccountActionLoading(scope.row.id)"
                            @click="handlePrimaryAccountAction(scope.row)"
                          >
                            {{ getPrimaryAccountActionLabel(scope.row) }}
                          </el-button>
                          <el-dropdown class="row-action-dropdown" trigger="click">
                            <el-button size="small">移动分组</el-button>
                            <template #dropdown>
                              <el-dropdown-menu>
                                <el-dropdown-item
                                  v-for="targetGroupId in availableMoveTargetGroups(scope.row)"
                                  :key="targetGroupId.id"
                                  @click="handleMoveAccountToGroup(scope.row, targetGroupId)"
                                >
                                  {{ targetGroupId.name }}
                                </el-dropdown-item>
                              </el-dropdown-menu>
                            </template>
                          </el-dropdown>
                          <el-dropdown class="row-action-dropdown" @command="(command) => handleMoreAction(command, scope.row)">
                            <el-button size="small">更多</el-button>
                            <template #dropdown>
                              <el-dropdown-menu>
                                <el-dropdown-item command="download-cookie">下载Cookie</el-dropdown-item>
                                <el-dropdown-item command="upload-cookie">上传Cookie</el-dropdown-item>
                              </el-dropdown-menu>
                            </template>
                          </el-dropdown>
                          <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                        </div>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

                <div v-else class="empty-data">
                  <el-empty :description="emptyGroupDescription" />
                </div>
              </section>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '添加账号' : '编辑账号'"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="!sseConnecting"
      :show-close="!sseConnecting"
    >
      <el-form :model="accountForm" label-width="80px" :rules="rules" ref="accountFormRef">
        <el-form-item label="平台" prop="platform">
          <el-select
            v-model="accountForm.platform"
            placeholder="请选择平台"
            style="width: 100%"
            :disabled="dialogType === 'edit' || sseConnecting"
          >
            <el-option label="快手" value="快手" />
            <el-option label="抖音" value="抖音" />
            <el-option label="视频号" value="视频号" />
            <el-option label="小红书" value="小红书" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dialogType === 'edit'" label="名称" prop="name">
          <el-input
            v-model="accountForm.name"
            placeholder="请输入账号名称"
            :disabled="sseConnecting"
          />
        </el-form-item>

        <div v-if="sseConnecting" class="qrcode-container">
          <div v-if="qrCodeData && !loginStatus" class="qrcode-wrapper">
            <p class="qrcode-tip">请使用对应平台 APP 扫码登录</p>
            <img :src="qrCodeData" alt="登录二维码" class="qrcode-image" />
          </div>
          <div v-else-if="!qrCodeData && !loginStatus" class="loading-wrapper">
            <el-icon class="is-loading"><Refresh /></el-icon>
            <span>{{ loginPromptMessage }}</span>
            <p v-if="loginPromptDetail" class="loading-tip">{{ loginPromptDetail }}</p>
          </div>
          <div v-else-if="loginStatus === '200'" class="success-wrapper">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>登录成功</span>
          </div>
          <div v-else-if="loginStatus === '500'" class="error-wrapper">
            <el-icon><CircleCloseFilled /></el-icon>
            <span>登录失败，请稍后再试</span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="handleDialogCancel">取消</el-button>
          <el-button
            type="primary"
            @click="submitAccountForm"
            :loading="confirmButtonLoading"
            :disabled="confirmButtonDisabled"
          >
            {{ confirmButtonText }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Refresh, CircleCheckFilled, CircleCloseFilled, Loading, Rank } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi } from '@/api/account'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import { http } from '@/utils/request'
import {
  ACCOUNT_GROUP_STORAGE_KEY,
  UNGROUPED_GROUP_ID,
  normalizeAccountGroupState,
  createAccountGroup,
  renameAccountGroup,
  deleteAccountGroup,
  moveAccountToGroup,
  reorderAccountGroup
} from '@/utils/accountGroups'

const accountStore = useAccountStore()
const appStore = useAppStore()

const platformTabs = [
  { name: 'all', label: '全部', platform: null },
  { name: 'kuaishou', label: '快手', platform: '快手' },
  { name: 'douyin', label: '抖音', platform: '抖音' },
  { name: 'channels', label: '视频号', platform: '视频号' },
  { name: 'xiaohongshu', label: '小红书', platform: '小红书' }
]

const SYSTEM_GROUP = {
  id: UNGROUPED_GROUP_ID,
  name: '未分组',
  isSystem: true
}

const activeTab = ref('all')
const searchKeyword = ref('')
const selectedGroupId = ref(UNGROUPED_GROUP_ID)
const pendingAddGroupId = ref(UNGROUPED_GROUP_ID)
const loginSessionId = ref('')
const editingGroupId = ref('')
const editingGroupName = ref('')
const draggingGroupId = ref('')
const dragHandleGroupId = ref('')
const groupNameInputRefs = new Map()
const openingAccountIds = ref([])
const loggingAccountIds = ref([])
const hasAccountSnapshot = ref(false)

const readStoredGroupState = () => {
  if (typeof window === 'undefined') {
    return { groups: [], assignments: {} }
  }

  try {
    const raw = window.localStorage.getItem(ACCOUNT_GROUP_STORAGE_KEY)
    if (!raw) {
      return { groups: [], assignments: {} }
    }

    const parsed = JSON.parse(raw)
    return {
      groups: Array.isArray(parsed?.groups) ? parsed.groups : [],
      assignments: parsed?.assignments && typeof parsed.assignments === 'object' ? parsed.assignments : {}
    }
  } catch (error) {
    console.error('读取账号分组缓存失败:', error)
    return { groups: [], assignments: {} }
  }
}

const writeStoredGroupState = (state) => {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(ACCOUNT_GROUP_STORAGE_KEY, JSON.stringify(state))
}

const accountGroupState = ref(readStoredGroupState())

let accountValidationRequestId = 0
let accountValidationEventSource = null

const fetchAccountsQuick = async () => {
  const res = await accountApi.getAccounts()
  if (res.code === 200 && res.data) {
    accountStore.setAccounts(res.data)
    hasAccountSnapshot.value = true
    return res.data
  }

  throw new Error(res.msg || '获取账号列表失败')
}

const closeAccountValidationStream = () => {
  if (accountValidationEventSource) {
    accountValidationEventSource.close()
    accountValidationEventSource = null
  }
}

const streamAccountValidationTask = (taskId, requestId) => {
  closeAccountValidationStream()

  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(accountApi.getAccountValidationStreamUrl(taskId))
    accountValidationEventSource = eventSource
    let settled = false

    const finalize = (callback, payload) => {
      if (settled) {
        return
      }
      settled = true
      if (accountValidationEventSource === eventSource) {
        accountValidationEventSource = null
      }
      eventSource.close()
      callback(payload)
    }

    eventSource.addEventListener('task-snapshot', (event) => {
      if (requestId !== accountValidationRequestId) {
        finalize(resolve, null)
        return
      }

      const snapshot = JSON.parse(event.data)
      accountStore.applyValidationTaskSnapshot(snapshot)

      if (snapshot.status === 'success') {
        accountStore.clearValidationState()
        finalize(resolve, snapshot)
        return
      }

      if (snapshot.status === 'error') {
        accountStore.clearValidationState()
        finalize(reject, new Error(snapshot.message || '账号状态刷新失败'))
      }
    })

    eventSource.onerror = () => {
      if (requestId !== accountValidationRequestId) {
        finalize(resolve, null)
        return
      }
      accountStore.clearValidationState()
      finalize(reject, new Error('账号状态刷新连接失败'))
    }
  })
}

const startProgressiveAccountValidation = async (accountIds = null) => {
  const requestId = ++accountValidationRequestId
  const payload = Array.isArray(accountIds) && accountIds.length ? { accountIds } : {}
  const res = await accountApi.startAccountValidation(payload)
  if (res.code !== 200 || !res.data?.taskId) {
    throw new Error(res.msg || '启动账号状态刷新失败')
  }

  accountStore.applyValidationTaskSnapshot(res.data)
  return await streamAccountValidationTask(res.data.taskId, requestId)
}

const refreshAccountsByIds = async (accountIds, { showSuccessMessage = false, successMessage = '账号信息已更新' } = {}) => {
  if (!Array.isArray(accountIds) || !accountIds.length) {
    return null
  }

  const task = await startProgressiveAccountValidation(accountIds)
  if (task && showSuccessMessage) {
    ElMessage.success(successMessage)
  }
  return task
}

const fetchAccounts = async ({ refreshListFirst = true, showSuccessMessage = true, showErrorMessage = true } = {}) => {
  if (appStore.isAccountRefreshing) return null

  appStore.setAccountRefreshing(true)

  try {
    if (refreshListFirst) {
      await fetchAccountsQuick()
    }

    const task = await startProgressiveAccountValidation()
    if (appStore.isFirstTimeAccountManagement) {
      appStore.setAccountManagementVisited()
    }
    if (task && showSuccessMessage) {
      ElMessage.success('账号状态刷新成功')
    }
    return task
  } catch (error) {
    console.error('账号状态刷新失败:', error)
    if (showErrorMessage) {
      ElMessage.error('账号状态刷新失败')
    }
    throw error
  } finally {
    appStore.setAccountRefreshing(false)
  }
}

onMounted(() => {
  const initializeAccounts = async () => {
    try {
      await fetchAccountsQuick()
    } catch (error) {
      console.error('快速获取账号数据失败:', error)
    }
  }

  initializeAccounts()
})

const getPlatformTagType = (platform) => {
  const typeMap = {
    快手: 'success',
    抖音: 'danger',
    视频号: 'warning',
    小红书: 'info'
  }
  return typeMap[platform] || 'info'
}

const ACCOUNT_STATUS_NORMAL = '正常'
const ACCOUNT_STATUS_ABNORMAL = '异常'

const isStatusClickable = (account) => {
  return account.status === ACCOUNT_STATUS_ABNORMAL && !account.isValidating
}

const getStatusTagType = (status) => {
  if (status === '验证中') {
    return 'info'
  } else if (status === '正常') {
    return 'success'
  } else {
    return 'danger'
  }
}

const handleStatusClick = (row) => {
  if (isStatusClickable(row)) {
    handleReLogin(row)
  }
}

const filterAccountsByKeyword = (accounts) => {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    return accounts
  }

  return accounts.filter((account) => {
    return (
      account.name.includes(keyword)
      || account.platform.includes(keyword)
      || String(account.id).includes(keyword)
    )
  })
}

const selectedPlatform = computed(() => {
  return platformTabs.find((tab) => tab.name === activeTab.value) || platformTabs[0]
})

const groupSidebarItems = computed(() => {
  const groups = Array.isArray(accountGroupState.value.groups) ? accountGroupState.value.groups : []
  return [
    ...groups.map((group) => ({ ...group, isSystem: false })),
    SYSTEM_GROUP
  ]
})

const getAccountGroupId = (account) => {
  return accountGroupState.value.assignments?.[String(account?.id ?? '')] || UNGROUPED_GROUP_ID
}

const getAccountGroupLabel = (account) => {
  const groupId = getAccountGroupId(account)
  return groupSidebarItems.value.find((group) => group.id === groupId)?.name || SYSTEM_GROUP.name
}

const groupAccountBuckets = computed(() => {
  const buckets = {}
  groupSidebarItems.value.forEach((group) => {
    buckets[group.id] = []
  })

  accountStore.accounts.forEach((account) => {
    const assignedGroupId = getAccountGroupId(account)
    const targetGroupId = buckets[assignedGroupId] ? assignedGroupId : UNGROUPED_GROUP_ID
    buckets[targetGroupId].push(account)
  })

  return buckets
})

const accountsInSelectedGroup = computed(() => {
  return groupAccountBuckets.value[selectedGroupId.value] || []
})

const currentPlatformAccounts = computed(() => {
  if (selectedPlatform.value.name === 'all') {
    return accountsInSelectedGroup.value
  }

  return accountsInSelectedGroup.value.filter((account) => account.platform === selectedPlatform.value.platform)
})

const visibleAccounts = computed(() => {
  return filterAccountsByKeyword(currentPlatformAccounts.value)
})

const currentGroupLabel = computed(() => {
  return groupSidebarItems.value.find((group) => group.id === selectedGroupId.value)?.name || SYSTEM_GROUP.name
})

const emptyGroupDescription = computed(() => {
  if (selectedGroupId.value === UNGROUPED_GROUP_ID) {
    return selectedPlatform.value.name === 'all'
      ? '未分组下暂无账号'
      : `未分组下暂无${selectedPlatform.value.label}账号`
  }

  return selectedPlatform.value.name === 'all'
    ? `${currentGroupLabel.value} 暂无账号`
    : `${currentGroupLabel.value} 暂无${selectedPlatform.value.label}账号`
})

const ensureSelectedGroup = () => {
  const availableGroupIds = new Set(groupSidebarItems.value.map((group) => group.id))
  if (availableGroupIds.has(selectedGroupId.value)) {
    return
  }

  selectedGroupId.value = accountGroupState.value.groups?.[0]?.id || UNGROUPED_GROUP_ID
}

watch(
  () => accountStore.accounts,
  (accounts) => {
    if (!hasAccountSnapshot.value) {
      ensureSelectedGroup()
      return
    }

    accountGroupState.value = normalizeAccountGroupState(accountGroupState.value, accounts)
    ensureSelectedGroup()
  },
  { deep: true, immediate: true }
)

watch(
  accountGroupState,
  (state) => {
    if (!hasAccountSnapshot.value) {
      return
    }
    writeStoredGroupState(state)
    ensureSelectedGroup()
  },
  { deep: true }
)

const handleSearch = () => {
}

const selectGroup = (groupId) => {
  selectedGroupId.value = groupId
}

const setGroupNameInputRef = (groupId, instance) => {
  if (instance) {
    groupNameInputRefs.set(groupId, instance)
  } else {
    groupNameInputRefs.delete(groupId)
  }
}

const focusGroupNameInput = async (groupId) => {
  await nextTick()
  const inputInstance = groupNameInputRefs.get(groupId)
  if (typeof inputInstance?.focus === 'function') {
    inputInstance.focus()
    return
  }

  const inputElement = inputInstance?.$el?.querySelector?.('input')
  inputElement?.focus?.()
  inputElement?.select?.()
}

const startEditingGroup = async (groupId) => {
  if (groupId === UNGROUPED_GROUP_ID) {
    return
  }

  const currentGroup = accountGroupState.value.groups.find((group) => group.id === groupId)
  if (!currentGroup) {
    return
  }

  editingGroupId.value = groupId
  editingGroupName.value = currentGroup.name
  await focusGroupNameInput(groupId)
}

const cancelGroupNameEdit = () => {
  editingGroupId.value = ''
  editingGroupName.value = ''
}

const commitGroupNameEdit = (groupId) => {
  if (editingGroupId.value !== groupId) {
    return
  }

  accountGroupState.value = renameAccountGroup(accountGroupState.value, groupId, editingGroupName.value)
  cancelGroupNameEdit()
}

const handleAddGroup = async () => {
  const result = createAccountGroup(accountGroupState.value, '新建分组')
  accountGroupState.value = result.state
  selectedGroupId.value = result.group.id
  editingGroupId.value = result.group.id
  editingGroupName.value = result.group.name
  await focusGroupNameInput(result.group.id)
}

const handleDeleteGroup = async (groupId) => {
  const targetGroup = accountGroupState.value.groups.find((group) => group.id === groupId)
  if (!targetGroup) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除分组 ${targetGroup.name} 吗？组内账号会回到未分组。`,
      '删除分组',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  accountGroupState.value = deleteAccountGroup(accountGroupState.value, groupId)
  if (selectedGroupId.value === groupId) {
    selectedGroupId.value = accountGroupState.value.groups[0]?.id || UNGROUPED_GROUP_ID
  }
  ElMessage.success('分组已删除')
}

const prepareGroupDrag = (groupId) => {
  dragHandleGroupId.value = groupId
}

const handleGroupDragStart = (event, groupId) => {
  if (groupId === UNGROUPED_GROUP_ID || dragHandleGroupId.value !== groupId) {
    event.preventDefault()
    return
  }

  draggingGroupId.value = groupId
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', groupId)
}

const handleGroupDrop = (event, groupId) => {
  if (groupId === UNGROUPED_GROUP_ID) {
    handleGroupDragEnd()
    return
  }

  const sourceGroupId = draggingGroupId.value || event.dataTransfer.getData('text/plain')
  if (!sourceGroupId || sourceGroupId === groupId) {
    handleGroupDragEnd()
    return
  }

  accountGroupState.value = reorderAccountGroup(accountGroupState.value, sourceGroupId, groupId)
  handleGroupDragEnd()
}

const handleGroupDragEnd = () => {
  draggingGroupId.value = ''
  dragHandleGroupId.value = ''
}

const getGroupAccounts = (groupId) => {
  return groupAccountBuckets.value[groupId] || []
}

const getGroupAccountCount = (groupId) => {
  return getGroupAccounts(groupId).length
}

const availableMoveTargetGroups = (row) => {
  const currentGroupId = getAccountGroupId(row)
  return groupSidebarItems.value.filter((group) => group.id !== currentGroupId)
}

const handleMoveAccountToGroup = (row, targetGroupId) => {
  const nextGroupId = typeof targetGroupId === 'object' ? targetGroupId.id : targetGroupId
  accountGroupState.value = moveAccountToGroup(accountGroupState.value, row.id, nextGroupId)

  ElMessage.success(
    nextGroupId === UNGROUPED_GROUP_ID
      ? `已将 ${row.name} 移到未分组`
      : `已将 ${row.name} 移到 ${groupSidebarItems.value.find((group) => group.id === nextGroupId)?.name || '目标分组'}`
  )
}

const dialogVisible = ref(false)
const dialogType = ref('add')
const accountFormRef = ref(null)

const accountForm = reactive({
  id: null,
  name: '',
  platform: '',
  status: '正常'
})

const rules = computed(() => ({
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  ...(dialogType.value === "edit"
    ? { name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }] }
    : {})
}))

const sseConnecting = ref(false)

const qrCodeData = ref('')
const loginStatus = ref('')
const browserLoginConfirming = ref(false)
const currentLoginMode = ref('idle')

const createLoginSessionId = () => {
  return `account-login-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

const ensureLoginSessionId = () => {
  if (!loginSessionId.value) {
    loginSessionId.value = createLoginSessionId()
  }
  return loginSessionId.value
}

const browserLoginConfirmPlatforms = ['小红书', '视频号', '抖音', '快手']

const browserLoginPlatformTypeMap = {
  小红书: '1',
  视频号: '2',
  抖音: '3',
  快手: '4'
}

const isBrowserConfirmPlatform = (platform) => browserLoginConfirmPlatforms.includes(platform)
const getPlatformType = (platform) => browserLoginPlatformTypeMap[platform] || '1'

const isBrowserConfirmPending = computed(() => {
  return currentLoginMode.value === 'browser' && sseConnecting.value && !loginStatus.value
})

const loginPromptMessage = computed(() => {
  if (isBrowserConfirmPending.value) {
    return '浏览器已打开，请在浏览器中扫码登录'
  }
  return '正在请求二维码...'
})

const loginPromptDetail = computed(() => {
  if (isBrowserConfirmPending.value) {
    return '完成扫码和授权后，点击下方按钮即可校验并保存 Cookie。'
  }
  return ''
})

const confirmButtonText = computed(() => {
  if (isBrowserConfirmPending.value) {
    return browserLoginConfirming.value ? '校验中' : '我已完成扫码'
  }
  if (sseConnecting.value) {
    return '登录中'
  }
  return '确认'
})

const confirmButtonLoading = computed(() => {
  if (isBrowserConfirmPending.value) {
    return browserLoginConfirming.value
  }
  return sseConnecting.value
})

const confirmButtonDisabled = computed(() => {
  if (isBrowserConfirmPending.value) {
    return browserLoginConfirming.value
  }
  return sseConnecting.value
})

const browserLoginPlatforms = browserLoginConfirmPlatforms

const waitingLoginMessage = computed(() => {
  if (isBrowserConfirmPlatform(accountForm.platform)) {
    return '浏览器已打开，请在浏览器中扫码登录'
  }
  return '正在请求二维码...'
})

const waitingLoginDetail = computed(() => {
  if (isBrowserConfirmPlatform(accountForm.platform)) {
    return '保持浏览器窗口打开，登录成功后会自动保存 Cookie。'
  }
  return ''
})

const handleAddAccount = () => {
  dialogType.value = 'add'
  pendingAddGroupId.value = selectedGroupId.value
  loginSessionId.value = ''
  Object.assign(accountForm, {
    id: null,
    name: '',
    platform: '',
  status: '正常'
  })
  resetLoginState()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogType.value = 'edit'
  loginSessionId.value = ''
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除账号 ${row.name} 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      try {
        const response = await accountApi.deleteAccount(row.id)

        if (response.code === 200) {
          accountStore.deleteAccount(row.id)
          accountGroupState.value = moveAccountToGroup(accountGroupState.value, row.id, UNGROUPED_GROUP_ID)
          ElMessage({
            type: 'success',
            message: '删除成功'
          })
        } else {
          ElMessage.error(response.msg || '删除失败')
        }
      } catch (error) {
        console.error('删除账号失败:', error)
        ElMessage.error('删除账号失败')
      }
    })
    .catch(() => {})
}

const isOpeningAccount = (accountId) => openingAccountIds.value.includes(accountId)
const isLoggingAccount = (accountId) => loggingAccountIds.value.includes(accountId)
const isPrimaryAccountActionLoading = (accountId) => isOpeningAccount(accountId) || isLoggingAccount(accountId)

const isLoginAccountAction = (row) => {
  if (!row) {
    return false
  }

  return row.status === ACCOUNT_STATUS_ABNORMAL
}

const getPrimaryAccountActionLabel = (row) => {
  return isLoginAccountAction(row) ? '登录' : '打开'
}

const getPrimaryAccountActionType = (row) => {
  return isLoginAccountAction(row) ? 'danger' : 'success'
}

const handlePrimaryAccountAction = async (row) => {
  if (isLoginAccountAction(row)) {
    await handleReLogin(row)
    return
  }

  await handleOpenAccount(row)
}

const handleOpenAccount = async (row) => {
  if (isOpeningAccount(row.id)) {
    return
  }

  openingAccountIds.value = [...openingAccountIds.value, row.id]

  try {
    const result = await accountApi.openAccountBrowser({ id: row.id })
    ElMessage.success(result.msg || `已打开 ${row.name} 的浏览器窗口`)
  } catch (error) {
    console.error('打开账号浏览器失败:', error)
    ElMessage.error(error?.message || '打开账号浏览器失败')
  } finally {
    openingAccountIds.value = openingAccountIds.value.filter((accountId) => accountId !== row.id)
  }
}

const handleMoreAction = (command, row) => {
  if (command === 'download-cookie') {
    handleDownloadCookie(row)
    return
  }

  if (command === 'upload-cookie') {
    handleUploadCookie(row)
  }
}

const handleDownloadCookie = (row) => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
  const downloadUrl = `${baseUrl}/downloadCookie?filePath=${encodeURIComponent(row.filePath)}`

  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `${row.name}_cookie.json`
  link.target = '_blank'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const handleUploadCookie = (row) => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.style.display = 'none'
  document.body.appendChild(input)

  input.onchange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    if (!file.name.endsWith('.json')) {
      ElMessage.error('请选择 JSON 格式的 Cookie 文件')
      document.body.removeChild(input)
      return
    }

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('id', row.id)
      formData.append('platform', row.platform)

      await http.upload('/uploadCookie', formData)

      ElMessage.success('Cookie 文件上传成功')
      await refreshAccountsByIds([row.id])
    } catch (error) {
      ElMessage.error('Cookie 文件上传失败')
    } finally {
      document.body.removeChild(input)
    }
  }

  input.click()
}

const handleReLogin = async (row) => {
  if (!row?.id || isLoggingAccount(row.id)) {
    return
  }

  loggingAccountIds.value = [...loggingAccountIds.value, row.id]

  dialogType.value = "edit"
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })

  resetLoginState()
  dialogVisible.value = true

  await nextTick()

  try {
    await startAccountLogin(row.platform)
  } catch (error) {
    console.error("启动登录流程失败:", error)
    ElMessage.error(error.message || "启动登录流程失败")
    resetLoginState()
  } finally {
    loggingAccountIds.value = loggingAccountIds.value.filter((accountId) => accountId !== row.id)
  }
}

const getDefaultAvatar = (name) => {
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random`
}

const getAccountAvatar = (account) => {
  return account?.avatarUrl || getDefaultAvatar(account?.name || '')
}

let eventSource = null

const closeSSEConnection = () => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

const resetLoginState = () => {
  closeSSEConnection()
  sseConnecting.value = false
  qrCodeData.value = ""
  loginStatus.value = ""
  browserLoginConfirming.value = false
  loginSessionId.value = ""
  currentLoginMode.value = "idle"
}

const handleDialogCancel = () => {
  dialogVisible.value = false
  resetLoginState()
}

const finishLoginSuccess = async (syncedAccountId = accountForm.id) => {
  const isEditMode = dialogType.value === 'edit'
  closeSSEConnection()
  dialogVisible.value = false
  sseConnecting.value = false
  browserLoginConfirming.value = false
  currentLoginMode.value = 'idle'

  ElMessage.success(dialogType.value === 'edit' ? '重新登录成功' : '账号添加成功')
  ElMessage({
    type: 'info',
    message: '正在同步账号信息...',
    duration: 0
  })

  if (syncedAccountId) {
    await refreshAccountsByIds([syncedAccountId])
  } else {
    await fetchAccounts()
  }
  ElMessage.closeAll()
  ElMessage.success('账号信息已更新')
}

const startBrowserLogin = async (platform) => {
  sseConnecting.value = true
  qrCodeData.value = ''
  loginStatus.value = ''
  browserLoginConfirming.value = false
  currentLoginMode.value = 'browser'

  const sessionId = ensureLoginSessionId()
  const res = await accountApi.startBrowserLogin({
    type: getPlatformType(platform),
    sessionId
  })

  if (!res.data?.started) {
    resetLoginState()
    throw new Error(res.msg || '浏览器登录启动失败')
  }

  if (res.data?.sessionId) {
    loginSessionId.value = res.data.sessionId
  }

  ElMessage.info(res.msg || '浏览器已打开，请扫码后点击完成按钮')
}

const confirmBrowserLogin = async () => {
  if (!isBrowserConfirmPending.value) {
    return
  }

  browserLoginConfirming.value = true
  try {
    const res = await accountApi.confirmBrowserLogin({
      type: getPlatformType(accountForm.platform),
      sessionId: loginSessionId.value,
      accountId: accountForm.id || undefined,
      accountName: accountForm.name || undefined
    })

    if (res.data?.confirmed) {
      const savedAccount = res.data?.account || null
      if (savedAccount?.id) {
        const syncedAccount = {
          id: savedAccount.id,
          name: savedAccount.userName || accountForm.name,
          platform: accountForm.platform,
          status: accountForm.status,
          avatarUrl: savedAccount.avatarUrl || ''
        }
        const existingSavedAccount = accountStore.accounts.some((account) => account.id === savedAccount.id)
        if (existingSavedAccount) {
          accountStore.updateAccount(savedAccount.id, syncedAccount)
        } else {
          accountStore.addAccount(syncedAccount)
        }
      }
      loginStatus.value = '200'
      if (dialogType.value === 'add' && savedAccount?.id && pendingAddGroupId.value !== UNGROUPED_GROUP_ID) {
        accountGroupState.value = moveAccountToGroup(
          accountGroupState.value,
          savedAccount.id,
          pendingAddGroupId.value
        )
      }
      await finishLoginSuccess(savedAccount?.id || accountForm.id)
      return
    }

    ElMessage.warning(res.msg || '尚未检测到登录成功，请完成扫码和授权后再试。')
  } catch (error) {
    console.error('浏览器登录确认失败:', error)
    loginStatus.value = '500'
    ElMessage.error('登录确认失败，请重试')
  } finally {
    browserLoginConfirming.value = false
  }
}

const startAccountLogin = async (platform) => {
  if (isBrowserConfirmPlatform(platform)) {
    await startBrowserLogin(platform)
    return
  }

  connectSSE(platform, loginSessionId.value || createLoginSessionId())
}

const connectSSE = (platform, sessionId) => {
  closeSSEConnection()

  sseConnecting.value = true
  qrCodeData.value = ''
  loginStatus.value = ''
  browserLoginConfirming.value = false
  currentLoginMode.value = 'sse'

  const type = getPlatformType(platform)
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
  const url = `${baseUrl}/login?type=${type}&sessionId=${encodeURIComponent(sessionId)}`

  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    const data = event.data

    if (!qrCodeData.value && data.length > 100) {
      if (data.startsWith('data:image')) {
        qrCodeData.value = data
      } else {
        qrCodeData.value = `data:image/png;base64,${data}`
      }
    } else if (data === '200' || data === '500') {
      loginStatus.value = data

      if (data === '200') {
        finishLoginSuccess()
      } else {
        closeSSEConnection()
        setTimeout(() => {
          resetLoginState()
        }, 2000)
      }
    }
  }

  eventSource.onerror = (error) => {
    console.error('SSE连接错误:', error)
    ElMessage.error('连接服务器失败，请稍后再试')
    closeSSEConnection()
    resetLoginState()
  }
}

const submitAccountForm = () => {
  accountFormRef.value.validate(async (valid) => {
    if (valid) {
      if (isBrowserConfirmPending.value) {
        await confirmBrowserLogin()
        return
      }

      if (dialogType.value === "add") {
        try {
          await startAccountLogin(accountForm.platform)
        } catch (error) {
          console.error('启动登录流程失败:', error)
          ElMessage.error(error.message || '启动登录流程失败')
          resetLoginState()
        }
      } else {
        try {
          const res = await accountApi.updateAccount({
            id: accountForm.id,
            type: Number(getPlatformType(accountForm.platform)),
            userName: accountForm.name
          })
          if (res.code === 200) {
            const updatedAccount = {
              id: accountForm.id,
              name: accountForm.name,
            platform: accountForm.platform,
            status: accountForm.status
          }
          accountStore.updateAccount(accountForm.id, updatedAccount)
          ElMessage.success('更新成功')
            dialogVisible.value = false
            fetchAccounts()
          } else {
            ElMessage.error(res.msg || '更新账号失败')
          }
        } catch (error) {
          console.error('更新账号失败:', error)
          ElMessage.error('更新账号失败')
        }
      }
    } else {
      return false
    }
  })
}

onBeforeUnmount(() => {
  accountValidationRequestId += 1
  closeAccountValidationStream()
})

onBeforeUnmount(() => {
  accountValidationRequestId += 1
  closeAccountValidationStream()
  accountStore.clearValidationState()
  appStore.setAccountRefreshing(false)
  closeSSEConnection()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.account-management {
  display: flex;
  flex-direction: column;
  min-height: 0;

  .page-header {
    margin-bottom: 18px;

    h1 {
      font-size: 30px;
      font-weight: 800;
      color: $text-primary;
      margin: 0;
    }
  }

  .account-tabs {
    background: transparent;
    border: 0;
    box-shadow: none;
    height: calc(100vh - 48px);
    min-height: 0;
    display: flex;
    flex-direction: column;

    .account-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
      padding: 12px 18px;
      border: 1px solid #e3e8f0;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 6px 18px rgba(21, 32, 51, 0.04);
    }

    .account-platform-tabs {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .account-platform-tab {
      height: 32px;
      padding: 0 16px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: #41506a;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;

      &:hover {
        color: #3b63f6;
        background: #eef3ff;
      }

      &.active {
        color: #fff;
        background: #3b63f6;
        box-shadow: 0 10px 18px rgba(59, 99, 246, 0.18);
      }
    }

    .account-toolbar-search {
      width: 320px;
      min-width: 0;

      .el-input {
        width: 100%;
      }
    }

    .account-toolbar-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      min-width: 0;
      white-space: nowrap;
      flex-shrink: 0;

      .el-icon.is-loading {
        animation: rotate 1s linear infinite;
      }
    }

    .account-tabs-nav {
      padding: 0;
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;

      :deep(.el-tabs__header) {
        display: none;
      }

      :deep(.el-tabs__content) {
        flex: 1;
        min-height: 0;
      }

      :deep(.el-tab-pane) {
        height: 100%;
        min-height: 0;
      }
    }
  }

  .account-list-container {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;

    .account-search {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 18px;
      padding: 12px 18px;
      border: 1px solid #e3e8f0;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 6px 18px rgba(21, 32, 51, 0.04);

      .el-input {
        width: 300px;
      }

      .action-buttons {
        display: flex;
        gap: 10px;

        .el-icon.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
    }

    .account-group-layout {
      display: flex;
      gap: 20px;
      min-height: 0;
      flex: 1;
    }

    .group-sidebar {
      width: 256px;
      flex: 0 0 256px;
      min-height: 0;
      padding: 18px;
      border: 1px solid #e3e8f0;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 8px 20px rgba(21, 32, 51, 0.05);
      overflow: hidden;
    }

    .group-list {
      height: 100%;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      padding-right: 2px;
    }

    .group-card {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 48px;
      padding: 10px 70px 10px 14px;
      border: 1px solid #e3e8f0;
      border-radius: 8px;
      background: #f8fafd;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        border-color: #d5e0ff;
        box-shadow: 0 8px 20px rgba(59, 99, 246, 0.08);

        .group-card-actions {
          opacity: 1;
        }
      }

      &.is-active {
        border-color: #3b63f6;
        background: #eef3ff;
      }

      &.is-system-group {
        border-style: dashed;
      }
    }

    .group-card-main {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: center;
    }

    .group-card-name-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      width: 100%;
      min-width: 0;
    }

    .group-card-name {
      flex: 1;
      min-width: 0;
      font-size: 15px;
      font-weight: 600;
      color: #111827;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .group-card-count {
      flex: 0 0 28px;
      width: 28px;
      padding: 0;
      border-radius: 999px;
      border: 1px solid #d5e0ff;
      background: #eef3ff;
      color: #3b63f6;
      font-size: 12px;
      line-height: 24px;
      text-align: center;
    }

    .group-card-actions {
      position: absolute;
      top: 50%;
      right: 12px;
      transform: translateY(-50%);
      display: flex;
      flex-direction: row;
      align-items: center;
      gap: 6px;
      opacity: 0;
      transition: opacity 0.2s ease;
      pointer-events: none;
    }

    .group-drag-handle,
    .group-delete-button {
      border: none;
      background: transparent;
      padding: 0;
      cursor: pointer;
    }

    .group-drag-handle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      color: #909399;

      &:hover {
        background: #f5f7fa;
        color: #606266;
      }
    }

    .group-delete-button {
      min-width: 34px;
      height: 24px;
      padding: 0 6px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      background: #fff1f0;
      color: #f56c6c;
      font-size: 12px;

      &:hover {
        background: #ffe5e3;
      }
    }

    .group-card:hover .group-card-actions,
    .group-card:focus-within .group-card-actions {
      opacity: 1;
      pointer-events: auto;
    }

    .group-account-panel {
      min-width: 0;
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      padding: 18px;
      border: 1px solid #e3e8f0;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 8px 20px rgba(21, 32, 51, 0.05);
    }

    .account-list {
      margin-bottom: 20px;
      flex: 1;
    }

    .row-action-group {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      flex-wrap: nowrap;

      :deep(.el-button) {
        margin: 0;
        min-height: 30px;
        padding: 7px 14px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
        vertical-align: middle;
      }

      .row-action-dropdown {
        display: inline-flex;
        align-items: center;

        :deep(.el-button) {
          min-height: 30px;
        }
      }
    }

    .empty-data {
      flex: 1;
      width: 100%;
      padding: 0;
      border: 1px dashed #ebeef5;
      border-radius: 12px;
      background: #fcfcfd;
      display: flex;
      align-items: center;
      justify-content: center;

      :deep(.el-empty) {
        margin: 0 auto;
      }
    }

    .account-list {
      flex: 1;
      min-height: 0;
      overflow: auto;
    }
  }

  .clickable-status {
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      transform: scale(1.05);
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
    }
  }

  .qrcode-container {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 250px;

    .qrcode-wrapper {
      text-align: center;

      .qrcode-tip {
        margin-bottom: 15px;
        color: #606266;
      }

      .qrcode-image {
        max-width: 200px;
        max-height: 200px;
        border: 1px solid #ebeef5;
        background-color: black;
      }
    }

    .loading-wrapper,
    .success-wrapper,
    .error-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;

      .el-icon {
        font-size: 48px;

        &.is-loading {
          animation: rotate 1s linear infinite;
        }
      }

      span {
        font-size: 16px;
      }

      .loading-tip {
        max-width: 260px;
        margin: 0;
        text-align: center;
        color: #909399;
        line-height: 1.5;
      }
    }

    .success-wrapper .el-icon {
      color: #67c23a;
    }

    .error-wrapper .el-icon {
      color: #f56c6c;
    }
  }
}

@media (max-width: 1280px) {
  .account-management {
    .account-list-container {
      .account-group-layout {
        flex-direction: column;
      }

      .group-sidebar {
        width: 100%;
        flex-basis: auto;
        padding-right: 0;
        padding-bottom: 16px;
        border-right: none;
        border-bottom: 1px solid #ebeef5;
      }
    }
  }
}
</style>
