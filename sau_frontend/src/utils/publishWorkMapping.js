import { splitPublishTextBlocks } from './publishTextBlocks.js'

const VIDEO_EXTENSIONS = new Set(['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v'])
const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])

function getLowerExtension(filename) {
  const normalized = String(filename || '').trim().toLowerCase()
  const dotIndex = normalized.lastIndexOf('.')
  return dotIndex >= 0 ? normalized.slice(dotIndex) : ''
}

export function splitPublishContents(rawContent) {
  return splitPublishTextBlocks(rawContent)
}

export function validatePublishContents({ rawContent, workCount }) {
  const contents = splitPublishContents(rawContent)

  if (contents.length !== workCount) {
    return {
      contents,
      error: `文案块数必须和作品数一致：当前 ${workCount} 个作品，需要 ${workCount} 个文案块`,
    }
  }

  return {
    contents,
    error: '',
  }
}

function isVideoEntry(entry) {
  if (!entry || (Array.isArray(entry.files) && entry.files.length > 0)) {
    return false
  }
  return VIDEO_EXTENSIONS.has(getLowerExtension(entry.name || entry.path))
}

function isImageEntry(entry) {
  if (!entry || (Array.isArray(entry.files) && entry.files.length > 0)) {
    return false
  }
  return IMAGE_EXTENSIONS.has(getLowerExtension(entry.name || entry.path))
}

function isImageFile(fileEntry) {
  return IMAGE_EXTENSIONS.has(getLowerExtension(fileEntry?.name || fileEntry?.path))
}

export function buildPublishWorks(fileEntries) {
  const normalizedEntries = Array.isArray(fileEntries) ? fileEntries : []
  const works = []

  for (const entry of normalizedEntries) {
    if (entry?.entryKind === 'note' || (Array.isArray(entry?.files) && entry.files.length > 0)) {
      const imageFiles = Array.isArray(entry?.files) ? entry.files : []
      if (imageFiles.length === 0) {
        throw new Error('图文文件夹不能为空')
      }
      if (!imageFiles.every(isImageFile)) {
        throw new Error('图文文件夹里只能包含图片文件')
      }
      works.push({
        kind: 'note',
        name: entry.name || '图文作品',
        filePaths: imageFiles.map((file) => file.path),
      })
      continue
    }

    if (isVideoEntry(entry)) {
      works.push({
        kind: 'video',
        name: entry.name || entry.path,
        filePaths: [entry.path],
      })
      continue
    }

    if (isImageEntry(entry)) {
      works.push({
        kind: 'note',
        name: entry.name || entry.path,
        filePaths: [entry.path],
      })
      continue
    }

    throw new Error(`无法识别作品类型：${entry?.name || entry?.path || '未知文件'}`)
  }

  return works
}

export function hasUnsupportedWeixinNoteWork(selectedAccounts, works) {
  const accounts = Array.isArray(selectedAccounts) ? selectedAccounts : []
  const hasWeixin = accounts.some((account) => Number(account?.type) === 2)
  const hasNote = (Array.isArray(works) ? works : []).some((work) => work?.kind === 'note')
  return hasWeixin && hasNote
}

export function isVideoFilename(filename) {
  return VIDEO_EXTENSIONS.has(getLowerExtension(filename))
}

export function isImageFilename(filename) {
  return IMAGE_EXTENSIONS.has(getLowerExtension(filename))
}
