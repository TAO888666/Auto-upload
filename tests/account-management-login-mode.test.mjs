import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viewPath = path.resolve('sau_frontend/src/views/AccountManagement.vue')
const source = fs.readFileSync(viewPath, 'utf8')

test('account management keeps browser-confirm login platforms configured', () => {
  assert.equal(source.includes('const browserLoginConfirmPlatforms = ['), true)
  assert.equal(source.includes("'视频号'"), true)
  assert.equal(source.includes("'快手'"), true)
})

test('account management waiting prompts reuse browser-confirm platform check', () => {
  assert.equal(
    source.includes('if (isBrowserConfirmPlatform(accountForm.platform)) {'),
    true,
  )
})

test('account management turns the primary action into open-or-login by row status', () => {
  assert.equal(source.includes('@click="handlePrimaryAccountAction(scope.row)"'), true)
  assert.equal(source.includes(':type="getPrimaryAccountActionType(scope.row)"'), true)
  assert.equal(source.includes('{{ getPrimaryAccountActionLabel(scope.row) }}'), true)
  assert.equal(source.includes('const ACCOUNT_STATUS_NORMAL = '), true)
  assert.equal(source.includes('const ACCOUNT_STATUS_ABNORMAL = '), true)
  assert.equal(source.includes('const isLoginAccountAction = (row) => {'), true)
  assert.equal(source.includes('const getPrimaryAccountActionLabel = (row) => {'), true)
  assert.equal(source.includes('const getPrimaryAccountActionType = (row) => {'), true)
  assert.equal(source.includes('const handlePrimaryAccountAction = async (row) => {'), true)
  assert.equal(source.includes('await handleOpenAccount(row)'), true)
  assert.equal(source.includes('handleReLogin(row)'), true)
})

test('account management assigns newly added accounts to the selected group before finishing login refresh', () => {
  const confirmedBranchStart = source.indexOf('if (res.data?.confirmed) {')
  const confirmedBranchEnd = source.indexOf("ElMessage.warning(res.msg || '尚未检测到登录成功，请完成扫码和授权后再试。')")
  const confirmedBranch = source.slice(confirmedBranchStart, confirmedBranchEnd)
  const moveIndex = confirmedBranch.indexOf('accountGroupState.value = moveAccountToGroup(')
  const finishIndex = confirmedBranch.indexOf('await finishLoginSuccess(')

  assert.notEqual(confirmedBranchStart, -1)
  assert.notEqual(confirmedBranchEnd, -1)
  assert.notEqual(moveIndex, -1)
  assert.notEqual(finishIndex, -1)
  assert.ok(
    moveIndex < finishIndex,
    'expected moveAccountToGroup to run before finishLoginSuccess in browser login confirmation',
  )
})

test('account management refreshes only the synced account after browser login success when account id is available', () => {
  assert.equal(source.includes('const finishLoginSuccess = async (syncedAccountId = accountForm.id) => {'), true)
  assert.equal(source.includes('if (syncedAccountId) {'), true)
  assert.equal(source.includes('await refreshAccountsByIds([syncedAccountId])'), true)
  assert.equal(source.includes('await finishLoginSuccess(savedAccount?.id || accountForm.id)'), true)
})

test('account management inserts newly confirmed browser-login accounts before group assignment', () => {
  assert.equal(source.includes('const existingSavedAccount = accountStore.accounts.some('), true)
  assert.equal(source.includes('accountStore.addAccount(syncedAccount)'), true)

  const confirmedBranchStart = source.indexOf('if (res.data?.confirmed) {')
  const confirmedBranchEnd = source.indexOf("ElMessage.warning(res.msg || '尚未检测到登录成功，请完成扫码和授权后再试。')")
  const confirmedBranch = source.slice(confirmedBranchStart, confirmedBranchEnd)
  const addIndex = confirmedBranch.indexOf('accountStore.addAccount(syncedAccount)')
  const moveIndex = confirmedBranch.indexOf('accountGroupState.value = moveAccountToGroup(')

  assert.ok(
    addIndex >= 0 && moveIndex >= 0 && addIndex < moveIndex,
    'expected new saved account to be inserted before assigning it to the selected group',
  )
})
