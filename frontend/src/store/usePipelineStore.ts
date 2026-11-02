import { create } from 'zustand'
import type { PipelineResult, PipelineStage } from '../types'
import { runPipeline, streamPipeline } from '../api/pipeline'

interface PipelineState {
  query: string
  result: PipelineResult | null
  stages: PipelineStage[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  progress: number

  // Actions
  setQuery: (query: string) => void
  runPipeline: (query: string) => Promise<void>
  streamPipeline: (query: string) => Promise<void>
  reset: () => void
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  query: '',
  result: null,
  stages: [],
  isLoading: false,
  isStreaming: false,
  error: null,
  progress: 0,

  setQuery: (query) => set({ query }),

  runPipeline: async (query) => {
    set({ isLoading: true, error: null, result: null, progress: 0 })
    try {
      const result = await runPipeline(query)
      set({ result, stages: result.stages, isLoading: false, progress: 1 })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message, isLoading: false })
    }
  },

  streamPipeline: async (query) => {
    set({ isStreaming: true, isLoading: true, error: null, result: null, stages: [], progress: 0 })
    try {
      let finalResult: PipelineResult | null = null
      let streamError: string | null = null
      const stagesList: PipelineStage[] = []

      await streamPipeline(query, (event) => {
        const type = event.type as string

        if (type === 'error') {
          streamError = (event.error as string) || 'Pipeline stage failed'
        }

        if (type === 'stage_complete') {
          stagesList.push({
            name: event.stage as string,
            success: event.success as boolean,
            duration_ms: event.duration_ms as number,
          })
          set({
            stages: [...stagesList],
            progress: event.progress as number,
          })
        }

        if (type === 'stage_start') {
          set({ progress: event.progress as number })
        }

        if (type === 'complete') {
          finalResult = {
            trace_id: '',
            query,
            success: event.success as boolean,
            total_duration_ms: event.total_duration_ms as number,
            stages: stagesList,
            answer: event.answer as string,
            papers: event.papers as never[],
            export_formats: [],
          }
        }
      })

      set({
        result: finalResult,
        error: streamError,
        isStreaming: false,
        isLoading: false,
        progress: streamError ? get().progress : 1,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message, isStreaming: false, isLoading: false })
    }
  },

  reset: () =>
    set({
      result: null,
      stages: [],
      isLoading: false,
      isStreaming: false,
      error: null,
      progress: 0,
    }),
}))
