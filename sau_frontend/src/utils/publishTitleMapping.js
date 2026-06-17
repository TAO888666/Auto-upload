import { splitPublishTextBlocks } from './publishTextBlocks.js'

export function splitPublishTitles(rawTitle) {
  return splitPublishTextBlocks(rawTitle)
}

export function validatePublishTitles({ rawTitle, workCount }) {
  const titles = splitPublishTitles(rawTitle)

  if (titles.length !== workCount) {
    return {
      titles,
      error: `标题块数必须和作品数一致：当前 ${workCount} 个作品，需要 ${workCount} 个标题块`,
    }
  }

  return {
    titles,
    error: '',
  }
}
