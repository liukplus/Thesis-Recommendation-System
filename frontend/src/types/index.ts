// Shared TypeScript types

export interface Paper {
  id: string
  title: string
  abstract: string | null
  authors: string | null
  doi: string | null
  venue: string | null
  year: number | null
  url: string | null
  pdf_url: string | null
  created_at: string
  updated_at: string
  score?: number
  rerank_score?: number
  rank?: number
}

export interface PipelineStage {
  name: string
  success: boolean
  duration_ms: number
}

export interface PipelineResult {
  trace_id: string
  query: string
  success: boolean
  total_duration_ms: number
  stages: PipelineStage[]
  answer: string
  papers: Paper[]
  export_formats: string[]
}

export interface PipelineRunRequest {
  query: string
  max_papers?: number
  stream?: boolean
}

export interface AgentToolCall {
  name: string
  arguments: Record<string, unknown>
  error?: string | null
}

export interface PlanStep {
  index: number
  description: string
  status: string
  tool?: string | null
}

export interface AgentResult {
  task_id: string
  status: string
  final_answer: string
  steps: number
  tool_calls: AgentToolCall[]
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
  plan: PlanStep[]
  error?: string | null
}

export interface AgentRunRequest {
  query: string
  max_steps?: number
  plan_first?: boolean
  stream?: boolean
}

export interface AgentStreamEvent {
  type: 'start' | 'plan' | 'thought' | 'tool_call' | 'tool_result' | 'tool_error' | 'final_answer' | 'error' | 'end'
  step?: number
  content?: string
  tool?: string
  arguments?: Record<string, unknown>
  result?: unknown
  error?: string
  call_id?: string
  steps?: PlanStep[]
  state?: Record<string, unknown>
}

export interface ToolInfo {
  name: string
  description: string
  category: string
  parameters: Record<string, unknown>
}

export interface HealthResponse {
  status: string
  timestamp: string
  version: string
}
