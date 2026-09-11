import { create } from 'zustand'
import type { AgentResult, AgentStreamEvent, PlanStep, AgentToolCall } from '../types'
import { runAgent, streamAgent, generatePlan } from '../api/agent'

interface AgentMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolName?: string
  isError?: boolean
}

interface AgentState {
  messages: AgentMessage[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  plan: PlanStep[]
  toolCalls: AgentToolCall[]
  result: AgentResult | null
  currentStep: number

  // Actions
  sendMessage: (query: string, stream?: boolean) => Promise<void>
  generatePlan: (query: string) => Promise<void>
  reset: () => void
}

let messageId = 0
function nextId() {
  return `msg_${++messageId}`
}

export const useAgentStore = create<AgentState>((set, get) => ({
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,
  plan: [],
  toolCalls: [],
  result: null,
  currentStep: 0,

  sendMessage: async (query, stream = true) => {
    // Add user message
    const userMessage: AgentMessage = {
      id: nextId(),
      role: 'user',
      content: query,
    }

    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true,
      error: null,
      toolCalls: [],
      currentStep: 0,
    }))

    if (stream) {
      // Streaming mode
      let assistantContent = ''
      const assistantMsgId = nextId()

      // Add placeholder assistant message
      set((state) => ({
        messages: [
          ...state.messages,
          { id: assistantMsgId, role: 'assistant', content: '' },
        ],
        isStreaming: true,
      }))

      try {
        await streamAgent(query, (event: AgentStreamEvent) => {
          const type = event.type

          if (type === 'plan') {
            set({ plan: event.steps || [] })
          }

          if (type === 'thought') {
            set({ currentStep: event.step || 0 })
          }

          if (type === 'tool_call') {
            const toolMsg: AgentMessage = {
              id: nextId(),
              role: 'system',
              content: `Calling tool: ${event.tool}`,
              toolName: event.tool,
            }
            set((state) => ({
              messages: [...state.messages, toolMsg],
              toolCalls: [
                ...state.toolCalls,
                {
                  name: event.tool || '',
                  arguments: event.arguments || {},
                },
              ],
            }))
          }

          if (type === 'tool_result') {
            const resultMsg: AgentMessage = {
              id: nextId(),
              role: 'tool',
              content: typeof event.result === 'string' ? event.result : JSON.stringify(event.result, null, 2),
              toolName: event.tool,
            }
            set((state) => ({
              messages: [...state.messages, resultMsg],
            }))
          }

          if (type === 'tool_error') {
            const errorMsg: AgentMessage = {
              id: nextId(),
              role: 'tool',
              content: `Error: ${event.error}`,
              toolName: event.tool,
              isError: true,
            }
            set((state) => ({
              messages: [...state.messages, errorMsg],
            }))
          }

          if (type === 'final_answer') {
            assistantContent = event.content || ''
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === assistantMsgId ? { ...m, content: assistantContent } : m
              ),
            }))
          }

          if (type === 'error') {
            set({ error: event.error || 'Unknown error' })
          }

          if (type === 'end') {
            set({ isStreaming: false, isLoading: false })
          }
        })
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        set({ error: message, isStreaming: false, isLoading: false })
      }
    } else {
      // Non-streaming mode
      try {
        const result = await runAgent(query)
        const assistantMessage: AgentMessage = {
          id: nextId(),
          role: 'assistant',
          content: result.final_answer,
        }
        set((state) => ({
          messages: [...state.messages, assistantMessage],
          result,
          plan: result.plan,
          toolCalls: result.tool_calls,
          isLoading: false,
        }))
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        set({ error: message, isLoading: false })
      }
    }
  },

  generatePlan: async (query) => {
    try {
      const result = await generatePlan(query)
      set({ plan: result.steps })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message })
    }
  },

  reset: () =>
    set({
      messages: [],
      isLoading: false,
      isStreaming: false,
      error: null,
      plan: [],
      toolCalls: [],
      result: null,
      currentStep: 0,
    }),
}))
