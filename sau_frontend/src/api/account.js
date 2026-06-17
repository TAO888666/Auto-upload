import { http } from '@/utils/request'

export const accountApi = {
  getValidAccounts() {
    return http.get('/getValidAccounts')
  },

  startAccountValidation(data = {}) {
    return http.post('/startAccountValidation', data)
  },

  getAccountValidationTask(taskId) {
    return http.get('/getAccountValidationTask', { taskId })
  },

  getAccountValidationStreamUrl(taskId) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
    return `${baseUrl}/accountValidationTasks/${encodeURIComponent(taskId)}/stream`
  },

  getAccounts() {
    return http.get('/getAccounts')
  },

  addAccount(data) {
    return http.post('/account', data)
  },

  startBrowserLogin(data) {
    return http.post('/login/start', data)
  },

  confirmBrowserLogin(data) {
    return http.post('/login/confirm', data)
  },

  openAccountBrowser(data) {
    return http.post('/account/open', data)
  },

  updateAccount(data) {
    return http.post('/updateUserinfo', data)
  },

  deleteAccount(id) {
    return http.get(`/deleteAccount?id=${id}`)
  }
}
