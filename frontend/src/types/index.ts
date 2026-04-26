export type TaskStatus = 'inbox' | 'assigned' | 'in_progress' | 'review' | 'quality_review' | 'done' | 'archived'
export type TaskPriority = 'critical' | 'high' | 'medium' | 'low'

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  board_id: string | null
  project_id: string | null
  assigned_agent_id: string | null
  parent_task_id: string | null
  tags: string[]
  estimated_tokens: number | null
  actual_tokens: number | null
  session_id: string | null
  is_template: boolean
  final_report: string | null
  created_at: string
  updated_at: string
}

export interface Agent {
  id: string
  name: string
  role: string
  status: 'idle' | 'working' | 'paused' | 'error'
  soul: Record<string, unknown> | null
  skills: string[]
  gateway_agent_id: string | null
  current_task_id: string | null
  tokens_used: number
  created_at: string
  updated_at: string
}

export interface TaskMessage {
  id: string
  task_id: string
  session_id: string | null
  role: 'user' | 'assistant' | 'system' | 'orchestrator'
  content: string
  agent_id: string | null
  agent_name: string | null
  tokens: number | null
  created_at: string
}
