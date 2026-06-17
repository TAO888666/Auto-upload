import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import {
  buildPublishAccountPayload,
  filterPublishAccountsByGroup,
  formatPublishAccountDisplayName,
  getAvailablePublishAccounts,
  getSelectedPublishAccounts,
  hasSelectedPlatformAccount,
} from '../sau_frontend/src/utils/publishAccountSelection.js'
import { UNGROUPED_GROUP_ID } from '../sau_frontend/src/utils/accountGroups.js'

const accounts = [
  { id: 11, type: 3, filePath: 'douyin-a.json', name: '抖音A', platform: '抖音' },
  { id: 12, type: 1, filePath: 'xhs-b.json', name: '小红书B', platform: '小红书' },
  { id: 13, type: 2, filePath: 'weixin-c.json', name: '视频号C', platform: '视频号' },
]

test('getAvailablePublishAccounts returns all accounts without platform filtering', () => {
  assert.deepEqual(getAvailablePublishAccounts(accounts), accounts)
})

test('getSelectedPublishAccounts preserves selected account order', () => {
  assert.deepEqual(
    getSelectedPublishAccounts(accounts, [13, 11]).map((account) => account.name),
    ['视频号C', '抖音A'],
  )
})

test('hasSelectedPlatformAccount detects selected platform membership', () => {
  assert.equal(hasSelectedPlatformAccount(accounts, [12, 13], 2), true)
  assert.equal(hasSelectedPlatformAccount(accounts, [12, 13], 3), false)
})

test('buildPublishAccountPayload returns account ids and legacy cookie file paths', () => {
  assert.deepEqual(
    buildPublishAccountPayload(accounts, [11, 13]),
    {
      accountIds: [11, 13],
      accountList: ['douyin-a.json', 'weixin-c.json'],
    },
  )
})

test('formatPublishAccountDisplayName shows platform and account name', () => {
  assert.equal(formatPublishAccountDisplayName(accounts[0]), '抖音 / 抖音A')
})

test('filterPublishAccountsByGroup supports all, grouped, and ungrouped account lists', () => {
  const groupState = {
    groups: [{ id: 'group_a', name: 'A组', createdAt: 1 }],
    assignments: {
      11: 'group_a',
      13: 'group_a',
    },
  }

  assert.deepEqual(
    filterPublishAccountsByGroup(accounts, groupState, 'all').map((account) => account.id),
    [11, 12, 13],
  )
  assert.deepEqual(
    filterPublishAccountsByGroup(accounts, groupState, 'group_a').map((account) => account.id),
    [11, 13],
  )
  assert.deepEqual(
    filterPublishAccountsByGroup(accounts, groupState, UNGROUPED_GROUP_ID).map((account) => account.id),
    [12],
  )
})

test('publish center account sidebar includes search first, then platform and group filters', () => {
  const publishCenterSource = fs.readFileSync(
    path.resolve('sau_frontend/src/views/PublishCenter.vue'),
    'utf8',
  )

  assert.equal(publishCenterSource.includes('class="account-sidebar-search-row"'), true)
  assert.equal(publishCenterSource.includes('class="account-sidebar-select-row"'), true)
  assert.equal(publishCenterSource.includes('v-model="accountSidebarGroupFilter"'), true)

  const searchRowIndex = publishCenterSource.indexOf('class="account-sidebar-search-row"')
  const selectRowIndex = publishCenterSource.indexOf('class="account-sidebar-select-row"')

  assert.ok(
    searchRowIndex >= 0 && selectRowIndex >= 0 && searchRowIndex < selectRowIndex,
    'expected search row to appear before the platform/group select row',
  )
})
