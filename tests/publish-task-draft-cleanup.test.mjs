import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const publishTaskStorePath = path.resolve('sau_frontend/src/stores/publishTask.js')
const source = fs.readFileSync(publishTaskStorePath, 'utf8')

test('publish task store clears tracked draft tabs when a task finishes successfully', () => {
  assert.equal(source.includes("import { removeStoredPublishDraftTabs } from '@/utils/publishDraftStorage'"), true)
  assert.equal(source.includes("removeStoredPublishDraftTabs(task.draftTabNames || [])"), true)
  assert.equal(source.includes('const trackTask = ({ taskId, label, mode, draftTabNames = [] }) => {'), true)
  assert.equal(source.includes('draftTabNames: Array.isArray(draftTabNames) ? [...draftTabNames] : [],'), true)
})
