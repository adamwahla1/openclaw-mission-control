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

// ── Memory ───────────────────────────────────────────────────────────────────

export interface Memory {
  id: string
  agent_id: string | null
  content: string
  memory_type: 'fact' | 'insight' | 'procedure' | 'experience' | 'preference'
  category: string
  source: string
  importance: number
  access_count: number
  decay_score: number
  tags: string[]
  connections: string[]
  created_at: string
  last_accessed_at: string | null
  updated_at: string
  outgoing_connections?: MemoryConnection[]
  incoming_connections?: MemoryConnection[]
}

export interface MemoryConnection {
  id: string
  source_memory_id: string
  target_memory_id: string
  connection_type: 'related' | 'causes' | 'contradicts' | 'supports' | 'derives'
  strength: number
  created_at: string
  target_content?: string
  target_type?: string
  source_content?: string
  source_type?: string
}

export interface MemoryGraphNode {
  id: string
  agent_id: string | null
  content: string
  memory_type: string
  category: string
  importance: number
  decay_score: number
  tags: string[]
  created_at: string
}

export interface MemoryGraphLink {
  source_memory_id: string
  target_memory_id: string
  connection_type: string
  strength: number
}

export interface MemoryGraphData {
  nodes: MemoryGraphNode[]
  links: MemoryGraphLink[]
}

export interface MemoryStats {
  total: number
  by_type: Record<string, number>
  by_category: Record<string, number>
  avg_importance: number
  avg_decay: number
  connections: number
}

// ── Office ───────────────────────────────────────────────────────────────────

export interface OfficeRoom {
  id: string
  name: string
  room_type: 'control' | 'desk' | 'meeting' | 'creative' | 'focus' | 'social'
  x: number
  y: number
  width: number
  height: number
  metadata: Record<string, unknown>
  agents?: OfficeAgent[]
}

export interface OfficeAgent {
  id: string
  agent_id: string
  room_id: string | null
  x: number
  y: number
  state: 'idle' | 'working' | 'thinking' | 'collaborating' | 'reviewing' | 'error'
  facing: 'up' | 'down' | 'left' | 'right'
  name: string
  role: string
  agent_status: string
}

export interface OfficeEvent {
  id: string
  agent_id: string | null
  room_id: string | null
  event_type: string
  data: Record<string, unknown>
  agent_name: string | null
  created_at: string
}
