import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viewPath = path.resolve('sau_frontend/src/views/AccountManagement.vue')
const viewSource = fs.readFileSync(viewPath, 'utf8')

test('account management uses a split layout with group sidebar and table area', () => {
  assert.equal(viewSource.includes('class="account-group-layout"'), true)
  assert.equal(viewSource.includes('class="group-sidebar"'), true)
  assert.equal(viewSource.includes('class="group-account-panel"'), true)
  assert.equal(viewSource.includes('当前分组'), false)
})

test('account management exposes group management interactions in the sidebar', () => {
  assert.equal(viewSource.includes('新建分组'), true)
  assert.equal(viewSource.includes('@dblclick.stop="startEditingGroup(group.id)"'), true)
  assert.equal(viewSource.includes('@click.stop="handleDeleteGroup(group.id)"'), true)
  assert.equal(viewSource.includes('@dragstart="handleGroupDragStart($event, group.id)"'), true)
  assert.equal(viewSource.includes('@drop="handleGroupDrop($event, group.id)"'), true)
})

test('account management keeps the search field in the same right-side toolbar group as the action buttons', () => {
  assert.equal(viewSource.includes('<div class="account-toolbar-actions">'), true)
  assert.equal(viewSource.includes('<div class="account-toolbar-search">'), true)
  assert.equal(viewSource.includes('gap: 12px;'), true)
  assert.equal(viewSource.includes('justify-content: space-between;'), true)
})

test('account management can move a single account to another group from the row actions', () => {
  assert.equal(viewSource.includes('移动分组'), true)
  assert.equal(viewSource.includes('handleMoveAccountToGroup(scope.row, targetGroupId)'), true)
  assert.equal(viewSource.includes('availableMoveTargetGroups(scope.row)'), true)
})
