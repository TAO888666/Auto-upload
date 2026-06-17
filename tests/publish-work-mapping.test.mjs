import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildPublishWorks,
  splitPublishContents,
  validatePublishContents,
  hasUnsupportedWeixinNoteWork,
} from '../sau_frontend/src/utils/publishWorkMapping.js'

test('buildPublishWorks maps video files and folder entries into ordered works', () => {
  const works = buildPublishWorks([
    { name: 'lesson-01.mp4', path: 'lesson-01.mp4' },
    {
      name: '案例图文',
      entryKind: 'note',
      files: [
        { name: '1.jpg', path: '1.jpg' },
        { name: '2.png', path: '2.png' },
      ],
    },
    { name: 'lesson-02.mov', path: 'lesson-02.mov' },
  ])

  assert.deepEqual(works, [
    { kind: 'video', name: 'lesson-01.mp4', filePaths: ['lesson-01.mp4'] },
    { kind: 'note', name: '案例图文', filePaths: ['1.jpg', '2.png'] },
    { kind: 'video', name: 'lesson-02.mov', filePaths: ['lesson-02.mov'] },
  ])
})

test('buildPublishWorks rejects invalid folder entries with non-image files', () => {
  assert.throws(
    () => buildPublishWorks([
      {
        name: '坏文件夹',
        entryKind: 'note',
        files: [
          { name: '1.jpg', path: '1.jpg' },
          { name: '2.mp4', path: '2.mp4' },
        ],
      },
    ]),
    /图文文件夹里只能包含图片文件/,
  )
})

test('buildPublishWorks treats a single image file as one note work', () => {
  const works = buildPublishWorks([
    { name: 'cover.jpg', path: 'cover.jpg' },
  ])

  assert.deepEqual(works, [
    { kind: 'note', name: 'cover.jpg', filePaths: ['cover.jpg'] },
  ])
})

test('validatePublishContents accepts matching content block count', () => {
  const result = validatePublishContents({
    rawContent: `视频文案第一行
视频文案第二行

图文正文第一行
图文正文第二行

第三条视频文案`,
    workCount: 3,
  })

  assert.deepEqual(result, {
    contents: [
      '视频文案第一行\n视频文案第二行',
      '图文正文第一行\n图文正文第二行',
      '第三条视频文案',
    ],
    error: '',
  })
})

test('splitPublishContents preserves line breaks inside one work block', () => {
  assert.deepEqual(
    splitPublishContents(`视频文案第一行
视频文案第二行

 图文正文第一行 
图文正文第二行`),
    ['视频文案第一行\n视频文案第二行', '图文正文第一行\n图文正文第二行'],
  )
})

test('hasUnsupportedWeixinNoteWork detects weixin accounts mixed with note works', () => {
  const selectedAccounts = [
    { id: 11, type: 3, platform: '抖音' },
    { id: 22, type: 2, platform: '视频号' },
  ]
  const works = [
    { kind: 'video', name: 'video-a', filePaths: ['a.mp4'] },
    { kind: 'note', name: 'note-a', filePaths: ['1.jpg', '2.jpg'] },
  ]

  assert.equal(hasUnsupportedWeixinNoteWork(selectedAccounts, works), true)
})
