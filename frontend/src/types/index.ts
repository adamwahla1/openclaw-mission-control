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

export interface Project {
  id: string
  name: string
  description: string | null
  status: string
  auto_bundled: number
  created_at: string
  updated_at: string
  // Joined data (when fetched with ?include=tasks)
  tasks?: Task[]
  task_count?: number
  files?: ProjectFile[]
  handovers?: Handover[]
}

export interface ProjectFile {
  id: string
  project_id: string
  name: string
  path: string | null
  file_type: string | null
  size_bytes: number | null
  content: string | null
  created_at: string
}

export interface Handover {
  id: string
  project_id: string
  title: string
  content_md: string
  agent_id: string | null
  created_at: string
}

export interface Debate {
  id: string
  title: string
  topic: string
  status: string
  max_rounds: number
  current_round: number
  conclusion_md: string | null
  needs_user_input: number
  created_at: string
  updated_at: string
  // Joined data
  participants?: DebateParticipant[]
  messages?: DebateMessage[]
  questions?: DebateQuestion[]
  participant_count?: number
}

export interface DebateParticipant {
  id: string
  debate_id: string
  agent_id: string
  role: string
  specialty: string
}

export interface DebateMessage {
  id: string
  debate_id: string
  agent_id: string | null
  round_number: number
  content: string
  response_to_id: string | null
  stance: string
  created_at: string
  agent_name?: string
}

export interface DebateQuestion {
  id: string
  debate_id: string
  question: string
  asked_by_agent_id: string | null
  user_response: string | null
  answered_at: string | null
  created_at: string
}
