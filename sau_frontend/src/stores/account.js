import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAccountStore = defineStore('account', () => {
  const accounts = ref([])

  const platformTypes = {
    1: '小红书',
    2: '视频号',
    3: '抖音',
    4: '快手'
  }

  const getStatusLabel = (statusCode) => {
    if (statusCode === -1) {
      return '验证中'
    }
    return statusCode === 1 ? '正常' : '异常'
  }

  const buildAccountRecord = (item, previousAccount = null) => ({
    id: item[0],
    type: item[1],
    filePath: item[2],
    name: item[3],
    status: getStatusLabel(item[4]),
    avatarUrl: item[5] || previousAccount?.avatarUrl || '',
    platform: platformTypes[item[1]] || '未知',
    isValidating: previousAccount?.isValidating || false,
    validationPhase: previousAccount?.validationPhase || 'idle'
  })

  const setAccounts = (accountsData) => {
    const previousAccounts = new Map(accounts.value.map((account) => [account.id, account]))
    accounts.value = accountsData.map((item) => buildAccountRecord(item, previousAccounts.get(item[0])))
  }

  const applyValidationTaskSnapshot = (taskData) => {
    const taskItems = new Map((taskData?.items || []).map((item) => [item.id, item]))
    accounts.value = accounts.value.map((account) => {
      const item = taskItems.get(account.id)
      if (!item) {
        return {
          ...account,
          isValidating: false,
          validationPhase: 'idle'
        }
      }

      return {
        ...account,
        status: item.phase === 'finished' ? getStatusLabel(item.status) : account.status,
        avatarUrl: item.avatarUrl || account.avatarUrl || '',
        isValidating: item.phase === 'running',
        validationPhase: item.phase || account.validationPhase
      }
    })
  }

  const clearValidationState = () => {
    accounts.value = accounts.value.map((account) => ({
      ...account,
      isValidating: false,
      validationPhase: 'idle'
    }))
  }

  const addAccount = (account) => {
    accounts.value.push(account)
  }

  const updateAccount = (id, updatedAccount) => {
    const index = accounts.value.findIndex((acc) => acc.id === id)
    if (index !== -1) {
      accounts.value[index] = { ...accounts.value[index], ...updatedAccount }
    }
  }

  const deleteAccount = (id) => {
    accounts.value = accounts.value.filter((acc) => acc.id !== id)
  }

  const getAccountsByPlatform = (platform) => {
    return accounts.value.filter((acc) => acc.platform === platform)
  }

  return {
    accounts,
    setAccounts,
    applyValidationTaskSnapshot,
    clearValidationState,
    addAccount,
    updateAccount,
    deleteAccount,
    getAccountsByPlatform
  }
})
