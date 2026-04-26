import { useEffect, useState, useRef } from 'react'
import { X, Bot, User, Cpu, Send, Zap, FileText, MessageSquare, Download, CheckCircle } from 'lucide-react'
import type { Task, TaskMessage } from '@/types'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

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
  onTaskUpdate?: (updated: Task) => void
}

type Tab = 'activity' | 'report'

// Minimal markdown renderer — handles headings, bold, italic, lists, hr, code
function MarkdownBlock({ content }: { content: string }) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let i = 0

  const renderInline = (text: string) => {
    // Bold+italic, bold, italic, backtick code
    const parts = text.split(/(\*\*\*.*?\*\*\*|\*\*.*?\*\*|`.*?`|\*.*?\*|_.*?_)/g)
    return parts.map((part, idx) => {
      if (part.startsWith('***') && part.endsWith('***')) return <strong key={idx}><em>{part.slice(3, -3)}</em></strong>
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={idx} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
      if ((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_'))) return <em key={idx}>{part.slice(1, -1)}</em>
      if (part.startsWith('`') && part.endsWith('`')) return <code key={idx} className="px-1 py-0.5 rounded bg-secondary text-[11px] font-mono">{part.slice(1, -1)}</code>
      return part
    })
  }

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) { elements.push(<div key={i} className="h-2" />); i++; continue }

    if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={i} className="text-xl font-bold text-foreground mt-5 mb-3 pb-2 border-b border-border">{trimmed.slice(2)}</h1>)
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={i} className="text-base font-semibold text-foreground mt-5 mb-2">{trimmed.slice(3)}</h2>)
    } else if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={i} className="text-sm font-semibold text-foreground mt-4 mb-1.5">{trimmed.slice(4)}</h3>)
    } else if (trimmed === '---') {
      elements.push(<hr key={i} className="border-border my-4" />)
    } else if (trimmed.startsWith('> ')) {
      elements.push(
        <blockquote key={i} className="border-l-2 border-primary/40 pl-3 py-0.5 my-2 text-sm text-muted-foreground italic">
          {renderInline(trimmed.slice(2))}
        </blockquote>
      )
    } else if (/^[-*]\s/.test(trimmed)) {
      // Collect consecutive list items
      const listItems: string[] = []
      while (i < lines.length && /^[-*]\s/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().slice(2))
        i++
      }
      elements.push(
        <ul key={`ul-${i}`} className="space-y-1 my-2 pl-1">
          {listItems.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm">
              <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground/50 shrink-0" />
              <span className="text-muted-foreground leading-relaxed">{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    } else if (/^\d+\.\s/.test(trimmed)) {
      // Ordered list
      const listItems: string[] = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^\d+\.\s/, ''))
        i++
      }
      elements.push(
        <ol key={`ol-${i}`} className="space-y-1.5 my-2 pl-1">
          {listItems.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2.5 text-sm">
              <span className="shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] flex items-center justify-center font-bold mt-0.5">{idx + 1}</span>
              <span className="text-muted-foreground leading-relaxed">{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      )
      continue
    } else if (trimmed.startsWith('_') && trimmed.endsWith('_') && trimmed.includes('Mission Control')) {
      // Footer line
      elements.push(<p key={i} className="text-[10px] text-muted-foreground/50 mt-4 italic">{renderInline(trimmed)}</p>)
    } else {
      elements.push(
        <p key={i} className="text-sm text-muted-foreground leading-relaxed">{renderInline(trimmed)}</p>
      )
    }
    i++
  }

  return <div className="space-y-0.5">{elements}</div>
}

export default function TaskDrawer({ task, onClose, onTaskUpdate }: Props) {
  const [messages, setMessages] = useState<TaskMessage[]>([])
  const [activeTab, setActiveTab] = useState<Tab>('activity')
  const [comment, setComment] = useState('')
  const [dispatching, setDispatching] = useState(false)
  const [dispatchResult, setDispatchResult] = useState<string | null>(null)
  const [currentTask, setCurrentTask] = useState<Task | null>(task)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Sync task prop → local state, auto-switch to report tab when report arrives
  useEffect(() => {
    if (!task) return
    setCurrentTask(task)
    if (task.final_report && activeTab === 'activity') {
      setActiveTab('report')
    }
  }, [task?.final_report, task?.status])

  useEffect(() => {
    setCurrentTask(task)
    if (task) { fetchMessages(); fetchTask() }
  }, [task?.id])

  useEffect(() => {
    if (!currentTask) return
    const isActive = currentTask.status === 'in_progress' || currentTask.status === 'assigned'
    if (!isActive) return
    const interval = setInterval(() => { fetchMessages(); fetchTask() }, 3000)
    return () => clearInterval(interval)
  }, [currentTask?.id, currentTask?.status])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchTask = async () => {
    if (!currentTask) return
    try {
      const updated = await api.get<Task>(`/tasks/${currentTask.id}`)
      setCurrentTask(updated)
      onTaskUpdate?.(updated)
      if (updated.final_report) setActiveTab('report')
    } catch { /* ignore */ }
  }

  const fetchMessages = async () => {
    if (!currentTask) return
    try {
      const msgs = await api.get<TaskMessage[]>(`/tasks/${currentTask.id}/messages`)
      setMessages(msgs)
    } catch { /* ignore */ }
  }

  const handleDispatch = async () => {
    if (!currentTask) return
    setDispatching(true)
    setDispatchResult(null)
    setActiveTab('activity')
    try {
      const res = await api.post<{ ok: boolean; message: string }>(
        '/orchestrator/dispatch', { task_id: currentTask.id }
      )
      setDispatchResult(res.message || 'Dispatched successfully')
    } catch (e: unknown) {
      setDispatchResult((e as Error).message)
    } finally {
      setDispatching(false)
    }
  }

  const handleMarkDone = async () => {
    if (!currentTask) return
    try {
      const updated = await api.patch<Task>(`/tasks/${currentTask.id}`, { status: 'done' })
      setCurrentTask(updated)
      onTaskUpdate?.(updated)
    } catch { /* ignore */ }
  }

  const handleDownloadReport = () => {
    if (!currentTask?.final_report) return
    const blob = new Blob([currentTask.final_report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentTask.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_report.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleComment = async () => {
    if (!currentTask || !comment.trim()) return
    await api.post(`/tasks/${currentTask.id}/comments`, { content: comment.trim() }).catch(() => {})
    setComment('')
  }

  const roleIcon = (role: string) => {
    if (role === 'assistant') return <Bot size={14} className="text-blue-400 mt-0.5 shrink-0" />
    if (role === 'orchestrator') return <Cpu size={14} className="text-purple-400 mt-0.5 shrink-0" />
    return <User size={14} className="text-muted-foreground mt-0.5 shrink-0" />
  }

  const t = currentTask
  if (!t) return null

  const hasReport = !!t.final_report
  const isActive = t.status === 'in_progress' || t.status === 'assigned'
  const isDone = t.status === 'done'
  const isDispatchable = !['done', 'archived'].includes(t.status)

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full z-50 w-[560px] flex flex-col bg-card border-l border-border shadow-2xl">

        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border shrink-0">
          <div className="flex-1 pr-4">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Badge variant={PRIORITY_VARIANT[t.priority] || 'secondary'}>{t.priority}</Badge>
              <Badge variant="outline">{STATUS_LABELS[t.status] || t.status}</Badge>
              {hasReport && (
                <Badge variant="success" className="gap-1">
                  <FileText size={10} />
                  Report ready
                </Badge>
              )}
            </div>
            <h2 className="text-base font-semibold leading-snug">{t.title}</h2>
            {t.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {t.tags.map(tag => (
                  <span key={tag} className="px-1.5 py-0.5 rounded text-xs bg-secondary text-secondary-foreground">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-secondary transition-colors shrink-0">
            <X size={15} />
          </button>
        </div>

        {/* Description */}
        {t.description && (
          <div className="px-5 py-3 border-b border-border shrink-0">
            <p className="text-sm text-muted-foreground leading-relaxed">{t.description}</p>
          </div>
        )}

        {/* Action bar */}
        <div className="px-5 py-3 border-b border-border flex items-center gap-2 shrink-0">
          {isDispatchable && (
            <Button
              size="sm"
              onClick={handleDispatch}
              disabled={dispatching || isActive}
              className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white shrink-0"
            >
              <Zap size={13} />
              {dispatching ? 'Dispatching…' : isActive ? 'Running…' : 'Dispatch'}
            </Button>
          )}
          {hasReport && !isDone && (
            <Button size="sm" variant="outline" onClick={handleMarkDone} className="gap-1.5 shrink-0">
              <CheckCircle size={13} />
              Mark Done
            </Button>
          )}
          {hasReport && (
            <Button size="sm" variant="ghost" onClick={handleDownloadReport} className="gap-1.5 shrink-0 ml-auto">
              <Download size={13} />
              Download .md
            </Button>
          )}
          {dispatchResult && (
            <p className="text-xs text-muted-foreground truncate">{dispatchResult}</p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border shrink-0">
          {[
            { id: 'activity' as Tab, label: 'Activity', icon: <MessageSquare size={13} /> },
            { id: 'report' as Tab, label: 'Report', icon: <FileText size={13} />, badge: hasReport },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-1.5 px-5 py-3 text-xs font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              {tab.icon}
              {tab.label}
              {tab.badge && (
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 ml-0.5" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'activity' ? (
          <>
            {/* Message stream */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-muted-foreground text-sm gap-2">
                  <Zap size={20} className="text-muted-foreground/30" />
                  <span>No agent activity yet</span>
                  <span className="text-xs">Hit Dispatch to assign this task to an agent</span>
                </div>
              ) : messages.map(msg => (
                <div key={msg.id} className={cn(
                  'flex gap-2 text-sm',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}>
                  {msg.role !== 'user' && roleIcon(msg.role)}
                  <div className={cn(
                    'max-w-[88%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed',
                    msg.role === 'user'
                      ? 'bg-blue-600/20 text-foreground rounded-tr-sm'
                      : msg.role === 'orchestrator'
                        ? 'bg-purple-600/15 text-foreground rounded-tl-sm'
                        : 'bg-secondary text-foreground rounded-tl-sm'
                  )}>
                    {msg.agent_name && (
                      <p className="text-[10px] text-muted-foreground font-semibold mb-1 uppercase tracking-wide">
                        {msg.agent_name}
                      </p>
                    )}
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {msg.role === 'user' && roleIcon(msg.role)}
                </div>
              ))}
              {isActive && (
                <div className="flex gap-2 items-center text-xs text-muted-foreground">
                  <Bot size={12} className="text-blue-400" />
                  <span className="flex gap-0.5">
                    <span className="animate-bounce" style={{ animationDelay: '0ms' }}>•</span>
                    <span className="animate-bounce" style={{ animationDelay: '150ms' }}>•</span>
                    <span className="animate-bounce" style={{ animationDelay: '300ms' }}>•</span>
                  </span>
                  <span>Agent working…</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Comment input */}
            <div className="p-4 border-t border-border flex gap-2 shrink-0">
              <Textarea
                placeholder="Add a note or instruction…"
                value={comment}
                onChange={e => setComment(e.target.value)}
                rows={2}
                className="resize-none text-sm"
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleComment() }}
              />
              <Button size="sm" className="self-end shrink-0" onClick={handleComment} disabled={!comment.trim()}>
                <Send size={14} />
              </Button>
            </div>
          </>
        ) : (
          /* Report tab */
          <div className="flex-1 overflow-y-auto">
            {hasReport ? (
              <div className="px-7 py-6">
                <MarkdownBlock content={t.final_report!} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                <FileText size={32} className="text-muted-foreground/20" />
                <p className="text-sm">No report yet</p>
                <p className="text-xs text-center max-w-52">
                  Dispatch this task to an agent — the final report will appear here automatically when the agent completes its work.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
