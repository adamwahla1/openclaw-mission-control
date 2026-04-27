import { useEffect, useState, useRef, useCallback } from 'react'
import {
  MessageSquare, Plus, ChevronRight, Send, HelpCircle,
  CheckCircle, Users, FileText, Brain, Sparkles,
} from 'lucide-react'
import { useDebateStore } from '@/store/debateStore'
import { api } from '@/lib/api'
import { cn, formatRelative } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import type { Debate, DebateMessage } from '@/types'

const STANCE_COLORS: Record<string, string> = {
  support: 'bg-green-500/10 border-green-500/30',
  oppose: 'bg-red-500/10 border-red-500/30',
  neutral: 'bg-secondary border-border',
}

const STANCE_BADGE: Record<string, 'success' | 'destructive' | 'secondary'> = {
  support: 'success',
  oppose: 'destructive',
  neutral: 'secondary',
}

const AGENT_COLORS = [
  'bg-blue-500', 'bg-purple-500', 'bg-emerald-500', 'bg-orange-500',
  'bg-pink-500', 'bg-cyan-500', 'bg-yellow-500', 'bg-red-500',
]

// Map role to a consistent color index
const ROLE_COLOR_INDEX: Record<string, number> = {
  proponent: 0,
  opponent: 1,
  moderator: 2,
}

function getAgentColor(agentId: string, role?: string): string {
  if (role && ROLE_COLOR_INDEX[role] !== undefined) {
    return AGENT_COLORS[ROLE_COLOR_INDEX[role]]
  }
  let hash = 0
  for (let i = 0; i < agentId.length; i++) hash = agentId.charCodeAt(i) + ((hash << 5) - hash)
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length]
}

function getInitials(name: string): string {
  return name.split(/[\s_-]/).map((w) => w[0]).join('').toUpperCase().slice(0, 2)
}

/** Simple markdown renderer for debate messages */
function MarkdownText({ content }: { content: string }) {
  const html = content
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-secondary text-xs font-mono">$1</code>')
    // Block quotes
    .replace(/^>\s?(.+)$/gm, '<blockquote class="border-l-2 border-primary/30 pl-3 text-muted-foreground italic">$1</blockquote>')
    // Headers
    .replace(/^### (.+)$/gm, '<h4 class="font-semibold text-sm mt-2 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="font-semibold mt-2 mb-1">$1</h3>')
    // Bullet lists
    .replace(/^- (.+)$/gm, '<li class="ml-3 list-disc">$1</li>')
    // Numbered lists
    .replace(/^\d+\.\s(.+)$/gm, '<li class="ml-3 list-decimal">$1</li>')
    // Paragraphs (double newlines)
    .replace(/\n\n/g, '</p><p class="mt-2">')
    // Single newlines
    .replace(/\n/g, '<br />')

  return (
    <div
      className="text-sm leading-relaxed prose-sm"
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  )
}

export default function DebateRoom() {
  const { debates, currentDebate, loading: _loading, fetchDebates, setCurrentDebate, updateDebate } = useDebateStore()
  const [createOpen, setCreateOpen] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const [newMessage, setNewMessage] = useState('')
  const [selectedAgent, setSelectedAgent] = useState('')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => { fetchDebates() }, [fetchDebates])

  // Auto-select first debate
  useEffect(() => {
    if (debates.length > 0 && !currentDebate) {
      setCurrentDebate(debates[0])
    }
  }, [debates, currentDebate, setCurrentDebate])

  const fetchDebateDetail = useCallback(async (id: string) => {
    try {
      const d = await api.get<Debate>(`/debates/${id}`)
      setCurrentDebate(d)
      updateDebate(id, d)
    } catch { /* ignore */ }
  }, [setCurrentDebate, updateDebate])

  useEffect(() => {
    if (currentDebate) {
      fetchDebateDetail(currentDebate.id)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentDebate?.messages?.length])

  const handleSelectDebate = async (debate: Debate) => {
    setCurrentDebate(debate)
    await fetchDebateDetail(debate.id)
  }

  const handleAdvance = async () => {
    if (!currentDebate) return
    setAdvancing(true)
    try {
      await api.post(`/debates/${currentDebate.id}/advance`)
      await fetchDebateDetail(currentDebate.id)
    } catch { /* ignore */ }
    finally { setAdvancing(false) }
  }

  const handleSimulate = async () => {
    if (!currentDebate) return
    setSimulating(true)
    try {
      // Start simulation (non-blocking: backend runs rounds with AI, we poll)
      api.post(`/debates/${currentDebate.id}/simulate`).catch(() => {})
      // Poll for updates every 2 seconds
      const pollInterval = setInterval(async () => {
        try {
          const d = await api.get<Debate>(`/debates/${currentDebate.id}`)
          setCurrentDebate(d)
          updateDebate(d.id, d)
          if (d.status === 'concluded') {
            clearInterval(pollInterval)
            setSimulating(false)
          }
        } catch { /* keep polling */ }
      }, 2000)
      // Safety timeout after 3 minutes
      setTimeout(() => { clearInterval(pollInterval); setSimulating(false) }, 180000)
    } catch { /* ignore */ }
  }

  const handleSendMessage = async () => {
    if (!currentDebate || !newMessage.trim()) return
    try {
      await api.post(`/debates/${currentDebate.id}/messages`, {
        agent_id: selectedAgent || null,
        content: newMessage.trim(),
        stance: 'neutral',
      })
      setNewMessage('')
      await fetchDebateDetail(currentDebate.id)
    } catch { /* ignore */ }
  }

  const handleAnswerQuestion = async (qid: string) => {
    if (!currentDebate || !answers[qid]?.trim()) return
    try {
      await api.patch(`/debates/${currentDebate.id}/questions/${qid}`, {
        user_response: answers[qid].trim(),
      })
      setAnswers((prev) => { const next = { ...prev }; delete next[qid]; return next })
      await fetchDebateDetail(currentDebate.id)
    } catch { /* ignore */ }
  }

  const handleCreated = (debate: Debate) => {
    setCurrentDebate(debate)
    fetchDebates()
  }

  const messages = currentDebate?.messages ?? []
  const participants = currentDebate?.participants ?? []
  const questions = currentDebate?.questions?.filter((q) => !q.user_response) ?? []
  const answeredQuestions = currentDebate?.questions?.filter((q) => q.user_response) ?? []

  // Group messages by round
  const rounds: Record<number, DebateMessage[]> = {}
  for (const msg of messages) {
    if (!rounds[msg.round_number]) rounds[msg.round_number] = []
    rounds[msg.round_number].push(msg)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Debate Room</h1>
          {debates.length > 0 && (
            <div className="flex items-center gap-1">
              {debates.map((d) => (
                <button
                  key={d.id}
                  onClick={() => handleSelectDebate(d)}
                  className={cn(
                    'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
                    currentDebate?.id === d.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-muted-foreground hover:text-foreground'
                  )}
                >
                  {d.title || d.topic.slice(0, 20)}
                </button>
              ))}
            </div>
          )}
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus size={14} className="mr-1.5" />
          New Debate
        </Button>
      </div>

      {/* Main content */}
      {!currentDebate ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center mb-4">
            <MessageSquare size={32} className="text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold mb-1">No debate selected</h2>
          <p className="text-muted-foreground text-sm max-w-sm mb-4">
            Start a new debate to watch agents deliberate on a topic.
          </p>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus size={14} className="mr-1.5" />
            New Debate
          </Button>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel — chat */}
          <div className="flex-1 flex flex-col border-r border-border">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {Object.keys(rounds).length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                  <MessageSquare size={32} className="mb-3 opacity-20" />
                  <p className="text-sm">No messages yet. Advance the round or simulate to begin.</p>
                </div>
              )}
              {Object.entries(rounds).sort(([a], [b]) => Number(a) - Number(b)).map(([round, msgs]) => (
                <div key={round}>
                  {/* Round divider */}
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-px flex-1 bg-border" />
                    <span className="text-xs font-medium text-muted-foreground">
                      Round {round}
                    </span>
                    <div className="h-px flex-1 bg-border" />
                  </div>
                  {/* Messages in this round */}
                  <div className="space-y-4">
                    {msgs.map((msg) => {
                      // Find participant to get role
                      const participant = participants.find((p) => p.agent_id === msg.agent_id)
                      const agentName = msg.agent_name ?? participant?.role ?? 'User'
                      const agentRole = participant?.role ?? ''
                      const isUser = !msg.agent_id
                      const color = isUser ? 'bg-primary' : getAgentColor(msg.agent_id ?? '', agentRole)
                      const stanceKey = msg.stance === 'support' ? 'support' : msg.stance === 'oppose' ? 'oppose' : 'neutral'
                      return (
                        <div key={msg.id} className="flex gap-3">
                          <div className={cn('w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 mt-0.5', color)}>
                            {isUser ? 'U' : getInitials(agentName)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1.5">
                              <span className="text-sm font-semibold">{agentName}</span>
                              {agentRole && (
                                <span className="text-[10px] text-muted-foreground font-medium bg-secondary px-1.5 py-0.5 rounded">
                                  {agentRole}
                                </span>
                              )}
                              <Badge variant={STANCE_BADGE[stanceKey] ?? 'secondary'} className="text-[10px]">
                                {stanceKey}
                              </Badge>
                              <span className="text-[10px] text-muted-foreground ml-auto">
                                {formatRelative(msg.created_at)}
                              </span>
                            </div>
                            <div className={cn('rounded-xl p-4 border', STANCE_COLORS[stanceKey] ?? STANCE_COLORS.neutral)}>
                              <MarkdownText content={msg.content} />
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Message input */}
            <div className="p-4 border-t border-border shrink-0">
              <div className="flex gap-2">
                <Select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="w-40 shrink-0"
                >
                  <option value="">You</option>
                  {participants.map((p) => (
                    <option key={p.agent_id} value={p.agent_id}>
                      {p.role}
                    </option>
                  ))}
                </Select>
                <div className="flex-1 flex gap-2">
                  <Input
                    placeholder="Type a message…"
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSendMessage()
                      }
                    }}
                  />
                  <Button size="icon" onClick={handleSendMessage} disabled={!newMessage.trim()}>
                    <Send size={14} />
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Right panel — controls */}
          <div className="w-80 shrink-0 overflow-y-auto p-4 space-y-4">
            {/* Debate info */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Debate Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Topic</label>
                  <p className="text-sm mt-0.5">{currentDebate.topic}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={currentDebate.status === 'concluded' ? 'success' : 'info'}>
                    {currentDebate.status}
                  </Badge>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Progress</label>
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${Math.min(100, (currentDebate.current_round / currentDebate.max_rounds) * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {currentDebate.current_round}/{currentDebate.max_rounds}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Actions */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={handleAdvance}
                disabled={advancing || currentDebate.status === 'concluded'}
              >
                <ChevronRight size={14} className="mr-1" />
                {advancing ? 'Advancing…' : 'Advance'}
              </Button>
              <Button
                size="sm"
                className="flex-1"
                onClick={handleSimulate}
                disabled={simulating || currentDebate.status === 'concluded'}
              >
                {simulating ? (
                  <>
                    <Brain size={14} className="mr-1 animate-pulse" />
                    Thinking…
                  </>
                ) : (
                  <>
                    <Sparkles size={14} className="mr-1" />
                    AI Debate
                  </>
                )}
              </Button>
            </div>
            {simulating && (
              <p className="text-[10px] text-muted-foreground text-center">
                AI agents are generating arguments… messages appear in real-time.
              </p>
            )}

            {/* Participants */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users size={14} />
                  Participants
                  <span className="text-muted-foreground font-normal">({participants.length})</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {participants.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-2">No participants yet</p>
                ) : (
                  participants.map((p) => {
                    const color = getAgentColor(p.agent_id, p.role)
                    const displayName = (p as any).name || p.role
                    return (
                      <div key={p.id} className="flex items-center gap-2.5">
                        <div className={cn('w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white', color)}>
                          {getInitials(displayName)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{displayName}</p>
                          <p className="text-[10px] text-muted-foreground truncate">{p.role} {p.specialty ? `· ${p.specialty.slice(0, 40)}` : ''}</p>
                        </div>
                      </div>
                    )
                  })
                )}
              </CardContent>
            </Card>

            {/* Questions */}
            {questions.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <HelpCircle size={14} />
                    Questions
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {questions.map((q) => (
                    <div key={q.id} className="space-y-2">
                      <p className="text-xs">{q.question}</p>
                      <div className="flex gap-1.5">
                        <Input
                          placeholder="Your answer…"
                          value={answers[q.id] ?? ''}
                          onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                          className="text-xs"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleAnswerQuestion(q.id)
                          }}
                        />
                        <Button
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={() => handleAnswerQuestion(q.id)}
                          disabled={!answers[q.id]?.trim()}
                        >
                          <Send size={12} />
                        </Button>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Answered questions */}
            {answeredQuestions.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <CheckCircle size={14} />
                    Answered
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {answeredQuestions.map((q) => (
                    <div key={q.id} className="space-y-1">
                      <p className="text-xs text-muted-foreground">{q.question}</p>
                      <p className="text-xs">{q.user_response}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Conclusion */}
            {currentDebate.status === 'concluded' && currentDebate.conclusion_md && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText size={14} />
                    Conclusion
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="bg-secondary rounded-lg p-4">
                    <MarkdownText content={currentDebate.conclusion_md} />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Create debate dialog */}
      <CreateDebateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  )
}

function CreateDebateDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (d: Debate) => void
}) {
  const [topic, setTopic] = useState('')
  const [maxRounds, setMaxRounds] = useState('3')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => { setTopic(''); setMaxRounds('3'); setError(null) }
  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const debate = await api.post<Debate>('/debates', {
        topic: topic.trim(),
        max_rounds: Number(maxRounds),
      })
      onCreated(debate)
      reset()
      onClose()
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Debate</DialogTitle>
          </DialogHeader>
          <div className="px-6 space-y-4">
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Topic</label>
              <Textarea
                autoFocus
                placeholder="What should the agents debate?"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                rows={3}
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Max Rounds</label>
              <Select value={maxRounds} onChange={(e) => setMaxRounds(e.target.value)}>
                <option value="2">2 rounds</option>
                <option value="3">3 rounds</option>
                <option value="5">5 rounds</option>
                <option value="7">7 rounds</option>
              </Select>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={submitting || !topic.trim()}>
              {submitting ? 'Creating…' : 'Start Debate'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
