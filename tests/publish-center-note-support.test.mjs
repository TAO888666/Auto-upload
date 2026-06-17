import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const publishCenterPath = path.resolve('sau_frontend/src/views/PublishCenter.vue')
const source = fs.readFileSync(publishCenterPath, 'utf8')

test('publish center routes the local upload area through file or directory import', () => {
  assert.equal(source.includes('class="custom-upload-overlay"'), true)
  assert.equal(source.includes('openFileUploadPicker'), true)
  assert.equal(source.includes('openDirectoryUploadPicker'), true)
  assert.equal(source.includes('@click.stop.prevent="openFileUploadPicker"'), true)
  assert.equal(source.includes('ref="uploadFilesInput"'), true)
  assert.equal(source.includes('webkitdirectory'), true)
  assert.equal(source.includes('@change="handleDirectoryUploadChange"'), true)
  assert.equal(source.includes('accept="video/*,image/*"'), true)
})

test('publish center resolves v-for template refs before opening native pickers', () => {
  assert.equal(source.includes('const resolveInputRefElement = (inputRefValue) => {'), true)
  assert.equal(source.includes('const resetInputRefValue = (inputRefValue) => {'), true)
  assert.equal(source.includes('Array.isArray(inputRefValue)'), true)
  assert.equal(source.includes("candidate?.tagName === 'INPUT'"), true)
  assert.equal(source.includes('const inputElement = resetInputRefValue(uploadFilesInput.value)'), true)
  assert.equal(source.includes('const inputElement = resetInputRefValue(folderUploadInput.value)'), true)
})

test('publish center includes a per-work content textarea', () => {
  assert.equal(source.includes('v-model="tab.content"'), true)
  assert.equal(source.includes('rawContent: tab.content'), true)
})

test('publish center exposes a global AI copy generation action for all tabs in parallel', () => {
  assert.equal(source.includes('class="global-ai-generate-btn"'), true)
  assert.equal(source.includes('@click="generatePublishCopy"'), true)
  assert.equal(source.includes('const generatePublishCopyForTab = async (tab) => {'), true)
  assert.equal(source.includes('const generatePublishCopy = async () => {'), true)
  assert.equal(source.includes('Promise.allSettled'), true)
  assert.equal(source.includes('tabs.map((tab) => generatePublishCopyForTab(tab))'), true)
  assert.equal(source.includes('@click="generatePublishCopy(tab)"'), false)
  assert.equal(source.includes('aiPublishApi.generatePublishCenterCopy'), true)
  assert.equal(source.includes('titleText'), true)
  assert.equal(source.includes('contentText'), true)
})

test('publish center shows a centered wait dialog while AI copy generation is running', () => {
  assert.equal(source.includes('class="ai-copy-wait-overlay"'), true)
  assert.equal(source.includes('<svg class="pl"'), true)
  assert.equal(source.includes('pl__ring--a'), true)
  assert.equal(source.includes('@keyframes ringA'), true)
  assert.equal(source.includes('AI 正在生成发布文案标题。请稍等，不要关闭页面'), true)
  assert.equal(source.includes('const aiCopyWaitVisible = ref(false)'), true)
  assert.equal(source.includes('aiCopyWaitVisible.value = true'), true)
  assert.equal(source.includes('aiCopyWaitVisible.value = false'), true)
})

test('publish center builds works before submit and blocks weixin note publish', () => {
  assert.equal(source.includes('buildPublishWorks(tab.fileList)'), true)
  assert.equal(source.includes('hasUnsupportedWeixinNoteWork(selectedAccountRecords, works)'), true)
  assert.equal(source.includes('contents,'), true)
})

test('publish center exposes a global publish mode and forwards headed choice', () => {
  assert.equal(source.includes("const globalPublishMode = ref('headless')"), true)
  assert.equal(source.includes('class="global-publish-mode-btn"'), true)
  assert.equal(source.includes('@click="toggleGlobalPublishMode"'), true)
  assert.equal(source.includes('const toggleGlobalPublishMode = () => {'), true)
  assert.equal(source.includes("ElMessage.success(globalPublishMode.value === 'headed' ? '当前为有头发布模式' : '当前为无头发布模式')"), true)
  assert.equal(source.includes("{{ globalPublishMode === 'headed' ? '发布显示' : '发布隐身' }}"), true)
  assert.equal(source.includes("headless: globalPublishMode.value !== 'headed'"), true)
})

test('publish center exposes a Douyin-only self declaration toggle and forwards it', () => {
  assert.equal(source.includes('v-model="tab.douyinSelfDeclaration"'), true)
  assert.equal(source.includes('label="自主声明"'), true)
  assert.equal(source.includes('douyinSelfDeclaration: false'), true)
  assert.equal(
    source.includes('douyinSelfDeclaration: tabHasSelectedPlatform(tab, 3) ? !!tab.douyinSelfDeclaration : false'),
    true,
  )
})

test('publish center preselects the first five recommended topics for new tabs', () => {
  assert.equal(source.includes('const DEFAULT_SELECTED_RECOMMENDED_TOPIC_COUNT = 5'), true)
  assert.equal(source.includes('const getDefaultSelectedTopics = (topics = recommendedTopics.value) => {'), true)
  assert.equal(source.includes('return normalizeTopicList(topics).slice(0, DEFAULT_SELECTED_RECOMMENDED_TOPIC_COUNT)'), true)
  assert.equal(source.includes('const createDefaultTabInit = () => ({'), true)
  assert.equal(source.includes('selectedTopics: getDefaultSelectedTopics(),'), true)
})

test('publish center uses numeric custom start days with now as default', () => {
  assert.equal(source.includes('el-input-number v-model="tab.startDays"'), true)
  assert.equal(source.includes(":min=\"0\""), true)
  assert.equal(source.includes("0=现在，1=明天，2=后天"), true)
  assert.equal(source.includes("startDays: 0"), true)
})
test('publish center persists publish drafts for all tabs and restores them on reload', () => {
  assert.equal(source.includes('loadStoredPublishDraftState'), true)
  assert.equal(source.includes('const loadPublishDraftState = () => {'), true)
  assert.equal(source.includes('const savePublishDraftState = () => {'), true)
  assert.equal(source.includes('activeTab: activeTab.value,'), true)
  assert.equal(source.includes('globalPublishMode: globalPublishMode.value,'), true)
  assert.equal(source.includes('tabs: tabs.map(serializePublishDraftTab)'), true)
  assert.equal(source.includes('watch(tabs, () => {'), true)
})

test('publish center clears only the published tab draft and can clear all drafts', () => {
  assert.equal(source.includes('const resetTabToDraftDefault = (tab) => {'), true)
  assert.equal(source.includes('const clearAllPublishDrafts = ({ preserveOneTab = true } = {}) => {'), true)
  assert.equal(source.includes('@click="clearAllPublishDrafts({ preserveOneTab: true })"'), true)
  assert.equal(source.includes('draftTabNames: [tab.name],'), true)
  assert.equal(source.includes('draftTabNames: tabs.map(tab => tab.name),'), true)
})

test('publish center blocks batch publish when the same account appears in multiple tabs', () => {
  assert.equal(source.includes('const findDuplicateBatchAccounts = () => {'), true)
  assert.equal(source.includes('const duplicateBatchAccounts = findDuplicateBatchAccounts()'), true)
  assert.equal(source.includes('同一个账号不能出现在多个 Tab 里'), true)
  assert.equal(source.includes('ElMessage.error(duplicateBatchAccounts.message)'), true)
})

test('publish center uses a three-column workspace layout without changing the top toolbar', () => {
  assert.equal(source.includes('class="publish-workspace"'), true)
  assert.equal(source.includes('class="account-sidebar"'), true)
  assert.equal(source.includes('class="upload-stage-panel"'), true)
  assert.equal(source.includes('class="content-config-panel"'), true)
})

test('publish center exposes inline account filters and checkbox selection in the sidebar', () => {
  assert.equal(source.includes('v-model="accountSidebarPlatformFilter"'), true)
  assert.equal(source.includes('v-model="accountSidebarKeyword"'), true)
  assert.equal(source.includes('filteredSidebarAccounts(tab)'), true)
  assert.equal(source.includes('class="account-sidebar-list"'), true)
  assert.equal(source.includes('class="account-sidebar-item"'), true)
  assert.equal(source.includes('@change="toggleSidebarAccountSelection(tab, account.id)"'), true)
})

test('publish center surfaces accounts selected in other tabs ahead with an orange state', () => {
  assert.equal(source.includes('const getOtherTabSelectedAccountLabels = (currentTab, accountId) => {'), true)
  assert.equal(source.includes('isSidebarAccountSelectedInOtherTabs(tab, account.id)'), true)
  assert.equal(source.includes("'selected-in-other-tab': isSidebarAccountSelectedInOtherTabs(tab, account.id)"), true)
  assert.equal(source.includes('const getSidebarAccountSortPriority = (tab, account) => {'), true)
  assert.equal(source.includes("Number(rightPriority) - Number(leftPriority)"), true)
  assert.equal(source.includes("class=\"account-sidebar-check\""), true)
  assert.equal(source.includes("class=\"other-tab-selected-tag\""), false)
  assert.equal(source.includes('>已选</el-tag>'), false)
  assert.equal(source.includes("#f59e0b"), true)
})

test('publish center hydrates account list on mount when the account store is empty', () => {
  assert.equal(source.includes("import { accountApi } from '@/api/account'"), true)
  assert.equal(source.includes('const syncPublishCenterAccounts = async () => {'), true)
  assert.equal(source.includes('const hydratePublishAccounts = async () => {'), true)
  assert.equal(source.includes('if (Array.isArray(accountStore.accounts) && accountStore.accounts.length > 0)'), true)
  assert.equal(source.includes('const res = await accountApi.getAccounts()'), true)
  assert.equal(source.includes('accountStore.setAccounts(res.data)'), true)
  assert.equal(source.includes('await syncPublishCenterAccounts()'), true)
  assert.equal(source.includes('onMounted(() => {'), true)
  assert.equal(source.includes('hydratePublishAccounts()'), true)
})

test('publish center shows open or login actions for sidebar accounts and confirms login in-place', () => {
  assert.equal(source.includes('class="account-sidebar-action-btn"'), true)
  assert.equal(source.includes('getSidebarAccountActionLabel(account)'), true)
  assert.equal(source.includes('handleSidebarAccountAction(account)'), true)
  assert.equal(source.includes('const STATUS_LABEL_NORMAL ='), true)
  assert.equal(source.includes('const openPublishCenterAccountBrowser = async (account) => {'), true)
  assert.equal(source.includes('const startPublishCenterAccountLogin = async (account) => {'), true)
  assert.equal(source.includes('const confirmPublishAccountLogin = async () => {'), true)
  assert.equal(source.includes('publishAccountLoginDialogVisible'), true)
  assert.equal(source.includes('accountApi.openAccountBrowser({ id: account.id })'), true)
  assert.equal(source.includes('accountApi.startBrowserLogin({'), true)
  assert.equal(source.includes('accountApi.confirmBrowserLogin({'), true)
  assert.equal(source.includes('await syncPublishCenterAccounts()'), true)
})
