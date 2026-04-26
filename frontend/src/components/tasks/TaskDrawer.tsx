import { useEffect, useState, useRef } from 'react'
import { X, Bot, User, Cpu, Send, Zap } from 'lucide-react'
import type { Task, TaskMessage } from '@/types'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

// Priority/status color maps
const PRIORITY_VARIANT: Record<string, 'destructive' | 'warning' | 'info' | 'success'> = {
  critical: 'destructive', high: 'warning', medium: 'info', low: 'success',
}
const STATUS_LABELS: Record<string, string> = {
  inbox: 'Inbox', assigned: 'Assigned', in_progress: 'In Progress',
  review: 'Review', quality_review: 'QA Review', done: 'Done', archived: 'Archived',
}

interface Props {
  task: Task | null
  onClose: () => void
}

export default function TaskDrawer({ task, onClose }: Props) {
  const [messages, setMessages] = useState<TaskMessage[]>([])
  const [comment, setComment] = useState('')
  const [dispatching, setDispatching] = useState(false)
  const [dispatchResult, setDispatchResult] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!task) return
    fetchMessages()
    // Poll if active
    const id = task.status === 'in_progress' || task.status === 'assigned'
      ? setInterval(fetchMessages, 3000)
      : null
    return () => { if (id) clearInterval(id) }
  }, [task?.id, task?.status])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchMessages = async () => {
    if (!task) return
    try {
      const msgs = await api.get<TaskMessage[]>(`/tasks/${task.id}/messages`)
      setMessages(msgs)
    } catch { /* ignore fetch errors */ }
  }

  const handleDispatch = async () => {
    if (!task) return
    setDispatching(true)
    setDispatchResult(null)
    try {
      const res = await api.post<{ ok: boolean; message: string }>('/orchestrator/dispatch', { task_id: task.id })
      setDispatchResult(res.message || 'Dispatched successfully')
    } catch (e: unknown) {
      setDispatchResult((e as Error).message)
    } finally {
      setDispatching(false)
    }
  }

  const handleComment = async () => {
    if (!task || !comment.trim()) return
    await api.post(`/tasks/${task.id}/comments`, { content: comment.trim() }).catch(() => {})
    setComment('')
    fetchMessages()
  }

  const roleIcon = (role: string) => {
    if (role === 'assistant') return <Bot size={14} className="text-blue-400 mt-0.5 shrink-0" />
    if (role === 'orchestrator') return <Cpu size={14} className="text-purple-400 mt-0.5 shrink-0" />
    return <User size={14} className="text-muted-foreground mt-0.5 shrink-0" />
  }

  if (!task) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full z-50 w-[520px] flex flex-col bg-card border-l border-border shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border">
          <div className="flex-1 pr-4">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={PRIORITY_VARIANT[task.priority] || 'secondary'}>
                {task.priority}
              </Badge>
              <Badge variant="outline">{STATUS_LABELS[task.status] || task.status}</Badge>
            </div>
            <h2 className="text-base font-semibold leading-snug">{task.title}</h2>
            {task.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {task.tags.map(t => (
                  <span key={t} className="px-1.5 py-0.5 rounded text-xs bg-secondary text-secondary-foreground">
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-secondary transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Description */}
        {task.description && (
          <div className="px-5 py-3 border-b border-border">
            <p className="text-sm text-muted-foreground leading-relaxed">{task.description}</p>
          </div>
        )}

        {/* Dispatch button */}
        <div className="px-5 py-3 border-b border-border">
          <Button
            size="sm"
            onClick={handleDispatch}
            disabled={dispatching || task.status === 'done' || task.status === 'archived'}
            className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Zap size={13} />
            {dispatching ? 'Dispatching...' : 'Dispatch to Orchestrator'}
          </Button>
          {dispatchResult && (
            <p className="mt-2 text-xs text-muted-foreground">{dispatchResult}</p>
          )}
        </div>

        {/* Message stream */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-24 text-muted-foreground text-sm">
              No agent activity yet
            </div>
          ) : messages.map(msg => (
            <div key={msg.id} className={cn(
              'flex gap-2 text-sm',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}>
              {msg.role !== 'user' && roleIcon(msg.role)}
              <div className={cn(
                'max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed',
                msg.role === 'user'
                  ? 'bg-blue-600/20 text-foreground rounded-tr-sm'
                  : msg.role === 'orchestrator'
                    ? 'bg-purple-600/20 text-foreground rounded-tl-sm'
                    : 'bg-secondary text-foreground rounded-tl-sm'
              )}>
                {msg.agent_name && (
                  <p className="text-[10px] text-muted-foreground font-medium mb-0.5">{msg.agent_name}</p>
                )}
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === 'user' && roleIcon(msg.role)}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Comment input */}
        <div className="p-4 border-t border-border flex gap-2">
          <Textarea
            placeholder="Add a note or instruction for the agent..."
            value={comment}
            onChange={e => setComment(e.target.value)}
            rows={2}
            className="resize-none text-sm"
          />
          <Button size="sm" className="self-end shrink-0" onClick={handleComment} disabled={!comment.trim()}>
            <Send size={14} />
          </Button>
        </div>
      </div>
    </>
  )
}
