import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeAccountGroupState,
  createAccountGroup,
  renameAccountGroup,
  deleteAccountGroup,
  moveAccountToGroup,
  reorderAccountGroup,
  getAccountsForGroup,
  UNGROUPED_GROUP_ID
} from '../sau_frontend/src/utils/accountGroups.js'

const sampleAccounts = [
  { id: 1, name: '账号1', platform: '抖音' },
  { id: 2, name: '账号2', platform: '快手' },
  { id: 3, name: '账号3', platform: '小红书' }
]

test('normalizeAccountGroupState keeps valid groups and strips invalid assignments', () => {
  const state = normalizeAccountGroupState(
    {
      groups: [
        { id: 'group-a', name: 'A组' },
        { id: 'group-b', name: 'B组' }
      ],
      assignments: {
        '1': 'group-a',
        '2': 'missing-group',
        '999': 'group-b'
      }
    },
    sampleAccounts
  )

  assert.deepEqual(state.groups.map((group) => group.id), ['group-a', 'group-b'])
  assert.deepEqual(state.assignments, { '1': 'group-a' })
})

test('group state can create rename reorder and delete business groups', () => {
  let state = normalizeAccountGroupState({ groups: [], assignments: {} }, sampleAccounts)

  const createResultA = createAccountGroup(state, 'A组')
  state = createResultA.state
  const createResultB = createAccountGroup(state, 'B组')
  state = createResultB.state

  assert.deepEqual(state.groups.map((group) => group.name), ['A组', 'B组'])

  state = renameAccountGroup(state, createResultA.group.id, '主账号组')
  assert.deepEqual(state.groups.map((group) => group.name), ['主账号组', 'B组'])

  state = reorderAccountGroup(state, createResultB.group.id, createResultA.group.id)
  assert.deepEqual(state.groups.map((group) => group.name), ['B组', '主账号组'])

  state = deleteAccountGroup(state, createResultB.group.id)
  assert.deepEqual(state.groups.map((group) => group.name), ['主账号组'])
})

test('accounts can move between groups and back to ungrouped', () => {
  let state = normalizeAccountGroupState(
    {
      groups: [
        { id: 'group-a', name: 'A组' },
        { id: 'group-b', name: 'B组' }
      ],
      assignments: {}
    },
    sampleAccounts
  )

  state = moveAccountToGroup(state, 1, 'group-a')
  state = moveAccountToGroup(state, 2, 'group-b')

  assert.deepEqual(getAccountsForGroup(state, sampleAccounts, 'group-a').map((account) => account.id), [1])
  assert.deepEqual(getAccountsForGroup(state, sampleAccounts, 'group-b').map((account) => account.id), [2])

  state = moveAccountToGroup(state, 1, UNGROUPED_GROUP_ID)
  assert.deepEqual(getAccountsForGroup(state, sampleAccounts, UNGROUPED_GROUP_ID).map((account) => account.id).sort((a, b) => a - b), [1, 3])
})
