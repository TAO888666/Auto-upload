import { getAccountsForGroup } from './accountGroups.js'

export function getAvailablePublishAccounts(accounts) {
  return Array.isArray(accounts) ? [...accounts] : []
}

export function filterPublishAccountsByGroup(accounts, groupState, groupId) {
  const normalizedAccounts = getAvailablePublishAccounts(accounts)
  if (!groupId || groupId === 'all') {
    return normalizedAccounts
  }

  const normalizedState = groupState && typeof groupState === 'object'
    ? groupState
    : { groups: [], assignments: {} }

  return getAccountsForGroup(normalizedState, normalizedAccounts, groupId)
}

export function getSelectedPublishAccounts(accounts, selectedAccountIds) {
  const accountMap = new Map((Array.isArray(accounts) ? accounts : []).map((account) => [account.id, account]))
  return (Array.isArray(selectedAccountIds) ? selectedAccountIds : [])
    .map((accountId) => accountMap.get(accountId))
    .filter(Boolean)
}

export function hasSelectedPlatformAccount(accounts, selectedAccountIds, platformType) {
  return getSelectedPublishAccounts(accounts, selectedAccountIds)
    .some((account) => Number(account.type) === Number(platformType))
}

export function buildPublishAccountPayload(accounts, selectedAccountIds) {
  const selectedAccounts = getSelectedPublishAccounts(accounts, selectedAccountIds)
  return {
    accountIds: selectedAccounts.map((account) => account.id),
    accountList: selectedAccounts.map((account) => account.filePath),
  }
}

export function formatPublishAccountDisplayName(account) {
  if (!account) {
    return ''
  }
  return `${account.platform} / ${account.name}`
}
