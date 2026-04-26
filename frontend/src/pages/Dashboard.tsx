import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { KanbanSquare, Users, Brain, Activity, Zap, Clock, ArrowRight } from 'lucide-react'
import { api } from '@/lib/api'
import { useSSE } from '@/hooks/useSSE'
import type { Task, Agent } from '@/types'
import { formatRelative } from '@/lib/utils'

interface Stats {
  activeTasks: number
  agentsOnline: number
  memories: number
  eventsToday: number
}

export default function Dashboard() {
  useSSE()
  const [stats, setStats] = useState<Stats>({ activeTasks: 0, agentsOnline: 0, memories: 0, eventsToday: 0 })
  const [recentTasks, setRecentTasks] = useState<Task[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const [tasks, agentList] = await Promise.all([
        api.get<Task[]>('/tasks'),
        api.get<Agent[]>('/agents'),
      ])
      const active = tasks.filter(t => ['assigned', 'in_progress', 'review', 'quality_review'].includes(t.status))
      setStats({
        activeTasks: active.length,
        agentsOnline: agentList.filter(a => a.status !== 'idle').length,
        memories: 0,
        eventsToday: tasks.filter(t => t.created_at?.startsWith(new Date().toISOString().slice(0, 10))).length,
      })
      setRecentTasks(tasks.slice(0, 8))
      setAgents(agentList.slice(0, 6))
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [])

  const STATUS_COLOR: Record<string, string> = {
    inbox: 'bg-slate-400', assigned: 'bg-blue-500', in_progress: 'bg-yellow-500',
    review: 'bg-orange-500', quality_review: 'bg-purple-500', done: 'bg-green-500', archived: 'bg-slate-600',
  }
  const PRIORITY_VARIANT: Record<string, 'destructive' | 'warning' | 'info' | 'success'> = {
    critical: 'destructive', high: 'warning', medium: 'info', low: 'success',
  }
  const AGENT_STATUS_COLOR: Record<string, string> = {
    idle: 'bg-slate-400', working: 'bg-green-400', paused: 'bg-yellow-400', error: 'bg-red-400',
  }

  const statCards = [
    { label: 'Active Tasks', value: stats.activeTasks, icon: <KanbanSquare size={20} />, color: 'text-blue-400' },
    { label: 'Agents Online', value: stats.agentsOnline, icon: <Users size={20} />, color: 'text-green-400' },
    { label: 'Memories', value: stats.memories, icon: <Brain size={20} />, color: 'text-purple-400' },
    { label: 'Events Today', value: stats.eventsToday, icon: <Activity size={20} />, color: 'text-orange-400' },
  ]

  return (
    <div className="p-6 space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <Card key={s.label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground font-medium">{s.label}</p>
                  <p className="text-3xl font-bold mt-1 tracking-tight">
                    {loading ? '—' : s.value}
                  </p>
                </div>
                <div className={`p-2.5 rounded-xl bg-secondary ${s.color}`}>{s.icon}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent tasks */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Recent Tasks</CardTitle>
              <a href="/tasks" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors">
                View all <ArrowRight size={12} />
              </a>
            </div>
          </CardHeader>
          <CardContent className="space-y-1 px-4 pb-4">
            {recentTasks.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                No tasks yet — create one in the Task Board
              </div>
            ) : recentTasks.map(task => (
              <div key={task.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-secondary/60 transition-colors cursor-pointer">
                <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_COLOR[task.status] || 'bg-slate-400'}`} />
                <span className="flex-1 text-sm truncate">{task.title}</span>
                <Badge variant={PRIORITY_VARIANT[task.priority] || 'secondary'} className="text-[10px] px-1.5">
                  {task.priority}
                </Badge>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {formatRelative(task.created_at)}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Agent roster */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Agent Roster</CardTitle>
              <a href="/agents" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors">
                View all <ArrowRight size={12} />
              </a>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 px-4 pb-4">
            {agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-muted-foreground text-sm gap-2">
                <Zap size={20} className="text-muted-foreground/40" />
                <span>No agents yet</span>
                <span className="text-xs text-center">Dispatch a task to create your first agent</span>
              </div>
            ) : agents.map(agent => (
              <div key={agent.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-secondary/60 transition-colors">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/30 to-purple-500/30 border border-border flex items-center justify-center text-xs font-bold">
                  {agent.name.slice(0, 2)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{agent.name}</p>
                  <p className="text-[10px] text-muted-foreground capitalize">{agent.role}</p>
                </div>
                <div className="flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${AGENT_STATUS_COLOR[agent.status] || 'bg-slate-400'}`} />
                  <span className="text-[10px] text-muted-foreground capitalize">{agent.status}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Gateway status bar */}
      <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-secondary/30 border border-border text-xs text-muted-foreground">
        <Clock size={12} />
        <span>Mission Control is running.</span>
        <span className="text-muted-foreground/50">·</span>
        <span>Connect to OpenClaw Gateway in Settings to enable live agent execution.</span>
      </div>
    </div>
  )
}
