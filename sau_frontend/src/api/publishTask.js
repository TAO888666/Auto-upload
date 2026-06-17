const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

export async function fetchPublishTaskStatus(taskId) {
  const response = await fetch(`${apiBaseUrl}/publishTasks/${encodeURIComponent(taskId)}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json'
    }
  })

  const data = await response.json().catch(() => null)
  if (!response.ok || !data || data.code !== 200) {
    throw new Error(data?.msg || `Failed to load publish task: ${taskId}`)
  }

  return data.data
}
