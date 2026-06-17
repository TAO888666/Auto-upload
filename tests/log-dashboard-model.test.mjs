import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_LOG_PANELS,
  normalizeLogDashboard,
} from '../sau_frontend/src/utils/logDashboardModel.js'

test('default log panels keep the expected four-panel order', () => {
  assert.deepEqual(
    DEFAULT_LOG_PANELS.map((panel) => panel.id),
    ['douyin', 'kuaishou', 'xiaohongshu', 'tencent'],
  )
})

test('normalizeLogDashboard fills defaults and preserves backend lines', () => {
  const result = normalizeLogDashboard({
    panels: [
      {
        id: 'douyin',
        name: '抖音',
        file: 'douyin.log',
        status: 'active',
        updatedAt: '2026-05-14 10:00:00',
        lineCount: 2,
        lines: ['line1', 'line2'],
      },
    ],
  })

  assert.equal(result.panels.length, 4)
  assert.equal(result.panels[0].id, 'douyin')
  assert.equal(result.panels[0].lines[1], 'line2')
  assert.equal(result.panels[1].id, 'kuaishou')
  assert.equal(result.panels[1].status, 'missing')
})
