import { http } from '@/utils/request'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

export const taskProgressApi = {
  getCurrentPublishTask: () => http.get('/publishTasks/current'),
  getPublishTask: (taskId) => http.get(`/publishTasks/${encodeURIComponent(taskId)}`),
  pausePublishTask: (taskId) => http.post(`/publishTasks/${encodeURIComponent(taskId)}/pause`),
  clearPublishTask: (taskId) => http.post(`/publishTasks/${encodeURIComponent(taskId)}/clear`),
  retryPublishTaskItem: (taskId, itemId) => http.post(`/publishTasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/retry`),
  getPublishTaskStreamUrl(taskId) {
    return `${apiBaseUrl}/publishTasks/${encodeURIComponent(taskId)}/stream`
  },
}
