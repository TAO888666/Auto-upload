import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viewPath = path.resolve('sau_frontend/src/views/AccountManagement.vue')
const apiPath = path.resolve('sau_frontend/src/api/account.js')
const storePath = path.resolve('sau_frontend/src/stores/account.js')

const viewSource = fs.readFileSync(viewPath, 'utf8')
const apiSource = fs.readFileSync(apiPath, 'utf8')
const storeSource = fs.readFileSync(storePath, 'utf8')

test('account management keeps cached status while validation runs row by row', () => {
  assert.equal(viewSource.includes("updatedAccount[4] = -1"), false)
  assert.equal(viewSource.includes("scope.row.isValidating ? 'is-loading' : ''"), true)
  assert.equal(viewSource.includes('v-if="scope.row.isValidating"'), true)
})

test('account management starts and streams account validation tasks over SSE', () => {
  assert.equal(viewSource.includes('accountApi.startAccountValidation(payload)'), true)
  assert.equal(viewSource.includes('new EventSource(accountApi.getAccountValidationStreamUrl(taskId))'), true)
  assert.equal(viewSource.includes('accountStore.applyValidationTaskSnapshot'), true)
})

test('account management no longer auto-validates all accounts on page entry', () => {
  assert.equal(viewSource.includes('validateAllAccountsInBackground'), false)
  assert.equal(viewSource.includes('setTimeout(() => {\n      validateAllAccountsInBackground()'), false)
  assert.equal(viewSource.includes('await fetchAccountsQuick()'), true)
  assert.equal(viewSource.includes('@click="fetchAccounts"'), true)
})

test('account management refreshes only changed accounts after upload or relogin', () => {
  assert.equal(viewSource.includes('const refreshAccountsByIds = async (accountIds'), true)
  assert.equal(viewSource.includes('await refreshAccountsByIds([row.id]'), true)
  assert.equal(viewSource.includes('await refreshAccountsByIds([accountForm.id]'), true)
})

test('account API exposes account validation task endpoints', () => {
  assert.equal(apiSource.includes('startAccountValidation(data = {})'), true)
  assert.equal(apiSource.includes("return http.post('/startAccountValidation', data)"), true)
  assert.equal(apiSource.includes('getAccountValidationStreamUrl(taskId)'), true)
  assert.equal(apiSource.includes('/accountValidationTasks/${encodeURIComponent(taskId)}/stream'), true)
})

test('account management exposes a dynamic primary action while keeping browser-open support', () => {
  assert.equal(viewSource.includes('@click="handlePrimaryAccountAction(scope.row)"'), true)
  assert.equal(viewSource.includes('{{ getPrimaryAccountActionLabel(scope.row) }}'), true)
  assert.equal(viewSource.includes(':type="getPrimaryAccountActionType(scope.row)"'), true)
  assert.equal(viewSource.includes('await handleOpenAccount(row)'), true)
  assert.equal(viewSource.includes('handleReLogin(row)'), true)
  assert.equal(apiSource.includes('openAccountBrowser(data)'), true)
  assert.equal(apiSource.includes("return http.post('/account/open', data)"), true)
})

test('account management tucks cookie actions into a more menu', () => {
  assert.equal(viewSource.includes('>更多</el-button>'), true)
  assert.equal(viewSource.includes('command="download-cookie"'), true)
  assert.equal(viewSource.includes('command="upload-cookie"'), true)
  assert.equal(viewSource.includes('handleMoreAction(command, scope.row)'), true)
  assert.equal(viewSource.includes('class="row-action-group"'), true)
  assert.equal(viewSource.includes('class="row-action-dropdown"'), true)
})

test('account store can apply incremental validation snapshots', () => {
  assert.equal(storeSource.includes('const applyValidationTaskSnapshot = (taskData) => {'), true)
  assert.equal(storeSource.includes("isValidating: item.phase === 'running'"), true)
  assert.equal(storeSource.includes('validationPhase: item.phase || account.validationPhase'), true)
  assert.equal(storeSource.includes("avatarUrl: item.avatarUrl || account.avatarUrl || ''"), true)
})

test('account management prefers persisted avatar urls with fallback placeholder', () => {
  assert.equal(viewSource.includes('const getAccountAvatar = (account) => {'), true)
  assert.equal(viewSource.includes("return account?.avatarUrl || getDefaultAvatar(account?.name || '')"), true)
  assert.equal(viewSource.includes(':src="getAccountAvatar(scope.row)"'), true)
})

test('account view and store use readable chinese status and platform labels', () => {
  assert.equal(storeSource.includes("return statusCode === 1 ? '正常' : '异常'"), true)
  assert.equal(storeSource.includes("return '验证中'"), true)
  assert.equal(storeSource.includes("1: '小红书'"), true)
  assert.equal(storeSource.includes("2: '视频号'"), true)
  assert.equal(storeSource.includes("3: '抖音'"), true)
  assert.equal(storeSource.includes("4: '快手'"), true)
  assert.equal(viewSource.includes("const ACCOUNT_STATUS_NORMAL = '正常'"), true)
  assert.equal(viewSource.includes("const ACCOUNT_STATUS_ABNORMAL = '异常'"), true)
  assert.equal(viewSource.includes("if (status === '正常')"), true)
  assert.equal(viewSource.includes("return account.status === ACCOUNT_STATUS_ABNORMAL && !account.isValidating"), true)
  assert.equal(viewSource.includes("{ name: 'all', label: '全部', platform: null }"), true)
  assert.equal(viewSource.includes('>添加账号</el-button>'), true)
})
