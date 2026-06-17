import test from 'node:test'
import assert from 'node:assert/strict'

import {
  splitPublishTitles,
  validatePublishTitles,
} from '../sau_frontend/src/utils/publishTitleMapping.js'

test('splitPublishTitles splits title blocks by blank lines', () => {
  assert.deepEqual(
    splitPublishTitles('标题A\n副标题A\n\n 标题B \n\n标题C'),
    ['标题A\n副标题A', '标题B', '标题C'],
  )
})

test('validatePublishTitles accepts matching title block count', () => {
  const result = validatePublishTitles({
    rawTitle: '标题A\n副标题A\n\n标题B',
    workCount: 2,
  })

  assert.deepEqual(result, {
    titles: ['标题A\n副标题A', '标题B'],
    error: '',
  })
})

test('validatePublishTitles rejects mismatched title block count', () => {
  const result = validatePublishTitles({
    rawTitle: '标题A\n\n标题B',
    workCount: 3,
  })

  assert.equal(
    result.error,
    '标题块数必须和作品数一致：当前 3 个作品，需要 3 个标题块',
  )
})
