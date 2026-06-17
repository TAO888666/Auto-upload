export function splitPublishTextBlocks(rawText) {
  const normalizedText = String(rawText || '')
    .replace(/\r\n?/g, '\n')
    .trim()

  if (!normalizedText) {
    return []
  }

  return normalizedText
    .split(/\n\s*\n+/)
    .map((block) => block
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .join('\n'))
    .filter(Boolean)
}
