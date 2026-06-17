export const ACCOUNT_GROUP_STORAGE_KEY = 'sau_account_groups_v1'
export const UNGROUPED_GROUP_ID = '__ungrouped__'

function buildEmptyState() {
  return {
    groups: [],
    assignments: {}
  }
}

function normalizeGroupName(name) {
  const normalized = String(name || '').trim()
  return normalized || '未命名分组'
}

function normalizeGroups(rawGroups) {
  if (!Array.isArray(rawGroups)) {
    return []
  }

  const seenIds = new Set()
  return rawGroups
    .map((group) => {
      const id = String(group?.id || '').trim()
      if (!id || seenIds.has(id)) {
        return null
      }
      seenIds.add(id)
      return {
        id,
        name: normalizeGroupName(group?.name),
        createdAt: Number(group?.createdAt) || Date.now()
      }
    })
    .filter(Boolean)
}

export function normalizeAccountGroupState(rawState, accounts) {
  const state = rawState && typeof rawState === 'object' ? rawState : buildEmptyState()
  const groups = normalizeGroups(state.groups)
  const validGroupIds = new Set(groups.map((group) => group.id))
  const validAccountIds = new Set((Array.isArray(accounts) ? accounts : []).map((account) => String(account?.id ?? '')))
  const assignments = {}

  const rawAssignments = state.assignments && typeof state.assignments === 'object' ? state.assignments : {}
  for (const [accountId, groupId] of Object.entries(rawAssignments)) {
    const normalizedAccountId = String(accountId).trim()
    const normalizedGroupId = String(groupId || '').trim()
    if (!validAccountIds.has(normalizedAccountId)) {
      continue
    }
    if (!validGroupIds.has(normalizedGroupId)) {
      continue
    }
    assignments[normalizedAccountId] = normalizedGroupId
  }

  return {
    groups,
    assignments
  }
}

function createGroupId() {
  return `group_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function createAccountGroup(state, name = '新建分组') {
  const nextGroup = {
    id: createGroupId(),
    name: normalizeGroupName(name),
    createdAt: Date.now()
  }

  return {
    state: {
      groups: [...state.groups, nextGroup],
      assignments: { ...state.assignments }
    },
    group: nextGroup
  }
}

export function renameAccountGroup(state, groupId, name) {
  return {
    groups: state.groups.map((group) => (
      group.id === groupId
        ? { ...group, name: normalizeGroupName(name) }
        : group
    )),
    assignments: { ...state.assignments }
  }
}

export function deleteAccountGroup(state, groupId) {
  const nextAssignments = { ...state.assignments }
  for (const [accountId, assignedGroupId] of Object.entries(nextAssignments)) {
    if (assignedGroupId === groupId) {
      delete nextAssignments[accountId]
    }
  }

  return {
    groups: state.groups.filter((group) => group.id !== groupId),
    assignments: nextAssignments
  }
}

export function moveAccountToGroup(state, accountId, groupId) {
  const normalizedAccountId = String(accountId)
  const nextAssignments = { ...state.assignments }

  if (!groupId || groupId === UNGROUPED_GROUP_ID) {
    delete nextAssignments[normalizedAccountId]
  } else {
    nextAssignments[normalizedAccountId] = groupId
  }

  return {
    groups: [...state.groups],
    assignments: nextAssignments
  }
}

export function reorderAccountGroup(state, sourceGroupId, targetGroupId) {
  const groups = [...state.groups]
  const sourceIndex = groups.findIndex((group) => group.id === sourceGroupId)
  const targetIndex = groups.findIndex((group) => group.id === targetGroupId)

  if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) {
    return {
      groups,
      assignments: { ...state.assignments }
    }
  }

  const [sourceGroup] = groups.splice(sourceIndex, 1)
  groups.splice(targetIndex, 0, sourceGroup)

  return {
    groups,
    assignments: { ...state.assignments }
  }
}

export function getAccountsForGroup(state, accounts, groupId) {
  const normalizedAccounts = Array.isArray(accounts) ? accounts : []
  if (groupId === UNGROUPED_GROUP_ID) {
    return normalizedAccounts.filter((account) => !state.assignments[String(account?.id ?? '')])
  }

  return normalizedAccounts.filter((account) => state.assignments[String(account?.id ?? '')] === groupId)
}
