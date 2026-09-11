import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
})

// Request interceptor: add auth token if available
api.interceptors.request.use((config) => {
  const traceId = localStorage.getItem('trace_id')
  if (traceId) {
    config.headers['X-Trace-Id'] = traceId
  }
  return config
})

// Response interceptor: handle errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default api

/**
 * Parse SSE stream from a fetch response.
 * Calls the callback for each event.
 */
export async function parseSSE(
  response: Response,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let eventData = ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        eventData = line.slice(6)
        if (eventData === '[DONE]') {
          return
        }
        try {
          const event = JSON.parse(eventData)
          onEvent(event)
        } catch (e) {
          console.warn('Failed to parse SSE event:', eventData)
        }
      }
    }
  }
}
