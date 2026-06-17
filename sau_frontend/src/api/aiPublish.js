import { http } from '@/utils/request'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

export const aiPublishApi = {
  loadConfig() {
    return http.get('/aiPublish/config')
  },

  saveConfig(data) {
    return http.post('/aiPublish/config', data)
  },

  testConfig(data) {
    return http.post('/aiPublish/config/test', data)
  },

  loadStorageUsage() {
    return http.get('/aiPublish/storage')
  },

  clearStorageTarget(target) {
    return http.post('/aiPublish/storage/cleanup', { target })
  },

  getModels() {
    return http.get('/aiPublish/models')
  },

  generatePublishCenterCopy(data) {
    return http.post('/aiPublish/publishCenter/generate', data)
  },

  uploadAttachment(file) {
    const formData = new FormData()
    formData.append('file', file)
    return http.upload('/aiPublish/uploads', formData)
  },

  startChat(data) {
    return http.post('/aiPublish/chat/start', data)
  },

  getChatTaskStreamUrl(taskId) {
    return `${apiBaseUrl}/aiPublish/chatTasks/${encodeURIComponent(taskId)}/stream`
  },

  confirmTask(data) {
    return http.post('/aiPublish/task/confirm', data)
  },
}
