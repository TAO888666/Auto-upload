import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viewPath = path.resolve('sau_frontend/src/views/MaterialManagement.vue')
const apiPath = path.resolve('sau_frontend/src/api/material.js')

const viewSource = fs.readFileSync(viewPath, 'utf8')
const apiSource = fs.readFileSync(apiPath, 'utf8')

test('material management exposes a guarded delete-all action', () => {
  assert.equal(viewSource.includes('全部删除'), true)
  assert.equal(viewSource.includes('@click="handleDeleteAll"'), true)
  assert.equal(viewSource.includes('const isDeletingAll = ref(false)'), true)
  assert.equal(viewSource.includes('const handleDeleteAll = () => {'), true)
  assert.equal(viewSource.includes('ElMessageBox.confirm'), true)
  assert.equal(viewSource.includes('materialApi.deleteAllMaterials()'), true)
  assert.equal(viewSource.includes('appStore.setMaterials([])'), true)
  assert.equal(viewSource.includes(':disabled="appStore.materials.length === 0"'), true)
})

test('material api calls the backend delete-all endpoint once', () => {
  assert.equal(apiSource.includes('deleteAllMaterials'), true)
  assert.equal(apiSource.includes("return http.post('/deleteAllFiles')"), true)
})
