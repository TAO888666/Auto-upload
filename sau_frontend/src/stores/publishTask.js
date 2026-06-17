import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElNotification } from 'element-plus'
import { fetchPublishTaskStatus } from '@/api/publishTask'
import { removeStoredPublishDraftTabs } from '@/utils/publishDraftStorage'

const POLL_INTERVAL_MS = 1500

export const usePublishTaskStore = defineStore('publishTask', () => {
  const pendingTasks = ref([])
  let pollTimer = null

  const stopPolling = () => {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
  }

  const notifyTaskFinished = (task, status) => {
    if (status === 'success') {
      removeStoredPublishDraftTabs(task.draftTabNames || [])
      ElNotification({
        title: '发布完成',
        message: task.message || `${task.label} 已全部完成`,
        type: 'success',
        duration: 4500,
      })
      return
    }

    ElNotification({
      title: '发布失败',
      message: task.message || `${task.label} 执行失败`,
      type: 'error',
      duration: 6000,
    })
  }

  const pollTasks = async () => {
    if (!pendingTasks.value.length) {
      stopPolling()
      return
    }

    const remainingTasks = []
    for (const trackedTask of pendingTasks.value) {
      try {
        const remoteTask = await fetchPublishTaskStatus(trackedTask.taskId)
        if (remoteTask.status === 'success' || remoteTask.status === 'error') {
          notifyTaskFinished(
            {
              ...trackedTask,
              message: remoteTask.message,
            },
            remoteTask.status,
          )
          continue
        }

        remainingTasks.push({
          ...trackedTask,
          status: remoteTask.status,
          message: remoteTask.message,
        })
      } catch (error) {
        remainingTasks.push(trackedTask)
      }
    }

    pendingTasks.value = remainingTasks
    if (!pendingTasks.value.length) {
      stopPolling()
    }
  }

  const ensurePolling = () => {
    if (pollTimer !== null || !pendingTasks.value.length) {
      return
    }
    pollTimer = window.setInterval(() => {
      void pollTasks()
    }, POLL_INTERVAL_MS)
  }

  const trackTask = ({ taskId, label, mode, draftTabNames = [] }) => {
    if (!taskId) {
      return
    }

    const exists = pendingTasks.value.some(task => task.taskId === taskId)
    if (exists) {
      return
    }

    pendingTasks.value.push({
      taskId,
      label,
      mode,
      draftTabNames: Array.isArray(draftTabNames) ? [...draftTabNames] : [],
      status: 'queued',
      message: 'publish task created',
    })

    ensurePolling()
    void pollTasks()
  }

  return {
    pendingTasks,
    trackTask,
    pollTasks,
    stopPolling,
  }
})
