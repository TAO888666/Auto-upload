export const DEFAULT_LOG_PANELS = [
  { id: 'douyin', name: '抖音', file: 'douyin.log' },
  { id: 'kuaishou', name: '快手', file: 'kuaishou.log' },
  { id: 'xiaohongshu', name: '小红书', file: 'xiaohongshu.log' },
  { id: 'tencent', name: '视频号', file: 'tencent.log' },
]

export function normalizeLogDashboard(data) {
  const incomingPanels = Array.isArray(data?.panels) ? data.panels : []
  const incomingMap = new Map(incomingPanels.map((panel) => [panel.id, panel]))

  return {
    panels: DEFAULT_LOG_PANELS.map((defaultPanel) => {
      const serverPanel = incomingMap.get(defaultPanel.id) || {}
      return {
        ...defaultPanel,
        status: 'missing',
        updatedAt: '',
        lineCount: 0,
        lines: ['暂无日志内容'],
        ...serverPanel,
        lines: Array.isArray(serverPanel.lines) && serverPanel.lines.length > 0
          ? serverPanel.lines
          : ['暂无日志内容'],
      }
    }),
  }
}

export function getLogStatusTagType(status) {
  switch (status) {
    case 'active':
      return 'primary'
    case 'idle':
      return 'info'
    case 'missing':
      return 'danger'
    default:
      return 'info'
  }
}
