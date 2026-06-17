const PUBLISH_DRAFT_STORAGE_KEY = 'sau_publish_center_drafts'
const PUBLISH_DRAFT_STORAGE_VERSION = 1

const canUseStorage = () => typeof window !== 'undefined' && !!window.localStorage

export const loadStoredPublishDraftState = () => {
  if (!canUseStorage()) {
    return null
  }

  try {
    const raw = window.localStorage.getItem(PUBLISH_DRAFT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return null
    }

    return parsed
  } catch (error) {
    console.error('failed to load publish drafts:', error)
    return null
  }
}

export const saveStoredPublishDraftState = (draftState) => {
  if (!canUseStorage()) {
    return
  }

  if (!draftState || !Array.isArray(draftState.tabs) || draftState.tabs.length === 0) {
    window.localStorage.removeItem(PUBLISH_DRAFT_STORAGE_KEY)
    return
  }

  window.localStorage.setItem(PUBLISH_DRAFT_STORAGE_KEY, JSON.stringify({
    version: PUBLISH_DRAFT_STORAGE_VERSION,
    ...draftState,
  }))
}

export const removeStoredPublishDraftState = () => {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.removeItem(PUBLISH_DRAFT_STORAGE_KEY)
}

export const removeStoredPublishDraftTabs = (tabNames = []) => {
  const normalizedTabNames = [...new Set(
    (Array.isArray(tabNames) ? tabNames : [])
      .map((tabName) => String(tabName || '').trim())
      .filter(Boolean),
  )]

  if (!normalizedTabNames.length) {
    return
  }

  const currentState = loadStoredPublishDraftState()
  if (!currentState || !Array.isArray(currentState.tabs)) {
    return
  }

  const nextTabs = currentState.tabs.filter((tab) => !normalizedTabNames.includes(String(tab?.name || '').trim()))
  if (!nextTabs.length) {
    removeStoredPublishDraftState()
    return
  }

  const nextActiveTab = normalizedTabNames.includes(currentState.activeTab)
    ? nextTabs[0]?.name || 'tab1'
    : currentState.activeTab

  saveStoredPublishDraftState({
    ...currentState,
    activeTab: nextActiveTab,
    tabs: nextTabs,
  })
}

export {
  PUBLISH_DRAFT_STORAGE_KEY,
  PUBLISH_DRAFT_STORAGE_VERSION,
}
