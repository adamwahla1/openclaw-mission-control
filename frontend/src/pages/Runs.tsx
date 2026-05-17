import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, CheckCircle2, Clock, PauseCircle, Play, RefreshCw, Square, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface Run {
  id: string
  title: string
  run_type: string
  status: string
  current_step?: string
  objective?: string
  result?: string
  error?: string
  created_at?: string
  updated_at?: string
}

interface RunEvent {
  id: string
  run_id: string
  event_type: string
  title?: string
  content?: string
  sequence: number
  created_at?: string
  data?: Record<string, unknown>
}

interface Approval {
  id: string
  action_type: string
  status: string
  run_id?: string
  tool_name?: string
  risk_level?: string
  request_payload?: Record<string, unknown>
}

const statusIcon: Record<string, ReactNode> = {
  completed: <CheckCircle2 size={16} className="text-green-400" />,
  failed: <XCircle size={16} className="text-red-400" />,
  cancelled: <Square size={16} className="text-muted-foreground" />,
  awaiting_approval: <PauseCircle size={16} className="text-yellow-400" />,
  running: <RefreshCw size={16} className="text-blue-400 animate-spin" />,
  queued: <Clock size={16} className="text-muted-foreground" />,
}

export default function Runs() {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('Project Builder Prototype')
  const [newObjective, setNewObjective] = useState('Build a small, safe improvement plan for Mission Control and produce a final report after approval.')
  const [error, setError] = useState<string | null>(null)

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? runs[0] ?? null,
    [runs, selectedId]
  )

  const selectedApprovals = useMemo(
    () => approvals.filter((approval) => approval.run_id === selectedRun?.id),
    [approvals, selectedRun?.id]
  )

  const fetchRuns = useCallback(async () => {
    const res = await fetch('/api/runs?limit=50')
    const data = await res.json()
    setRuns(data)
    setSelectedId((current) => current ?? data[0]?.id ?? null)
  }, [])

  const fetchApprovals = useCallback(async () => {
    const res = await fetch('/api/approvals?status=pending')
    setApprovals(await res.json())
  }, [])

  const refresh = useCallback(async () => {
    await Promise.all([fetchRuns(), fetchApprovals()])
  }, [fetchRuns, fetchApprovals])

  const fetchEvents = useCallback(async (runId: string) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/runs/${runId}/events`)
      const data = await res.json()
      setEvents(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh().catch((e) => setError(String(e)))
  }, [refresh])

  useEffect(() => {
    if (selectedRun?.id) fetchEvents(selectedRun.id)
  }, [selectedRun?.id, fetchEvents])

  useEffect(() => {
    const es = new EventSource('/events')
    const handler = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        if (data.run_id === selectedRun?.id) {
          setEvents((current) => [...current.filter((item) => item.id !== data.id), data].sort((a, b) => a.sequence - b.sequence))
        }
        refresh()
      } catch {
        // ignore malformed events
      }
    }
    const approvalHandler = () => {
      refresh()
    }
    es.addEventListener('run.event', handler)
    es.addEventListener('approval.created', approvalHandler)
    es.addEventListener('approval.approved', approvalHandler)
    es.addEventListener('approval.rejected', approvalHandler)
    return () => es.close()
  }, [selectedRun?.id, refresh])

  const createProjectBuilderRun = async () => {
    if (!newObjective.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_type: 'project_builder',
          title: newTitle.trim() || 'Project Builder Run',
          objective: newObjective.trim(),
          metadata: { source: 'runs.prototype_ui' },
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const run = await res.json()
      setSelectedId(run.id)
      await refresh()
      await fetchEvents(run.id)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const cancelRun = async () => {
    if (!selectedRun) return
    await fetch(`/api/runs/${selectedRun.id}/cancel`, { method: 'POST' })
    await refresh()
    await fetchEvents(selectedRun.id)
  }

  const resumeRun = async () => {
    if (!selectedRun) return
    await fetch(`/api/runs/${selectedRun.id}/resume`, { method: 'POST' })
    await refresh()
    await fetchEvents(selectedRun.id)
  }

  const decideApproval = async (approval: Approval, decision: 'approve' | 'reject') => {
    if (!selectedRun) return
    const res = await fetch(`/api/approvals/${approval.id}/${decision}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decided_by: 'user' }),
    })
    if (!res.ok) {
      setError(await res.text())
      return
    }
    await refresh()
    await fetchEvents(selectedRun.id)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center">
            <Activity size={20} className="text-muted-foreground" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Runs</h1>
            <p className="text-sm text-muted-foreground">Start, inspect, approve, and replay native runtime work</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw size={14} className="mr-1.5" />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Play size={18} className="text-muted-foreground" />
            <CardTitle className="text-base">Start Project Builder</CardTitle>
          </div>
          <CardDescription>Runs offline with placeholders until OpenRouter is configured, then upgrades to live model output.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Run title" />
          <textarea
            value={newObjective}
            onChange={(e) => setNewObjective(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder="What should Project Builder plan, draft, review, and report?"
          />
          <Button onClick={createProjectBuilderRun} disabled={creating || !newObjective.trim()}>
            {creating ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <Play size={14} className="mr-1.5" />}
            Start Run
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)] gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Runs</CardTitle>
            <CardDescription>{runs.length} recorded</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {runs.length === 0 && <p className="text-sm text-muted-foreground">No runs yet.</p>}
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedId(run.id)}
                className={cn(
                  'w-full text-left rounded-lg border px-3 py-3 transition-colors',
                  selectedRun?.id === run.id ? 'bg-accent border-accent' : 'hover:bg-accent/50'
                )}
              >
                <div className="flex items-center gap-2">
                  {statusIcon[run.status] ?? statusIcon.queued}
                  <span className="font-medium text-sm truncate">{run.title}</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{run.run_type}</span>
                  <span>{run.status}</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">{selectedRun?.title ?? 'Run Timeline'}</CardTitle>
                <CardDescription>
                  {selectedRun ? `${selectedRun.status}${selectedRun.current_step ? ` - ${selectedRun.current_step}` : ''}` : 'Select a run'}
                </CardDescription>
              </div>
              {selectedRun && (
                <div className="flex items-center gap-2">
                  {selectedRun.status === 'awaiting_approval' && (
                    <Button variant="outline" size="sm" onClick={resumeRun}>Resume</Button>
                  )}
                  {['queued', 'running', 'awaiting_approval'].includes(selectedRun.status) && (
                    <Button variant="outline" size="sm" onClick={cancelRun}>Cancel</Button>
                  )}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!selectedRun && <p className="text-sm text-muted-foreground">No run selected.</p>}
            {selectedRun && (
              <div className="space-y-4">
                {selectedRun.error && (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                    {selectedRun.error}
                  </div>
                )}

                {selectedApprovals.map((approval) => {
                  const draftPreview = approval.request_payload?.draft_preview
                  return (
                    <div key={approval.id} className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-medium text-yellow-200">
                            <PauseCircle size={15} />
                            Approval required: {approval.tool_name || approval.action_type}
                          </div>
                          <div className="text-xs text-yellow-100/80 mt-1">Risk: {approval.risk_level || 'write'}</div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => decideApproval(approval, 'approve')}>Approve</Button>
                          <Button variant="outline" size="sm" onClick={() => decideApproval(approval, 'reject')}>Reject</Button>
                        </div>
                      </div>
                      {typeof draftPreview === 'string' && (
                        <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-background/70 p-3 text-xs text-muted-foreground">
                          {draftPreview}
                        </pre>
                      )}
                    </div>
                  )
                })}

                {selectedRun.result && (
                  <div>
                    <div className="text-sm font-medium mb-2">Final Report</div>
                    <pre className="whitespace-pre-wrap break-words rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground max-h-96 overflow-auto">
                      {selectedRun.result}
                    </pre>
                  </div>
                )}

                {loading && <p className="text-sm text-muted-foreground">Loading events...</p>}
                {!loading && events.length === 0 && <p className="text-sm text-muted-foreground">No events recorded.</p>}
                {events.map((event) => (
                  <div key={event.id} className="border-l border-border pl-4 pb-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">{event.title || event.event_type}</div>
                      <div className="text-xs text-muted-foreground">#{event.sequence}</div>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">{event.event_type}</div>
                    {event.content && (
                      <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground max-h-72 overflow-auto">
                        {event.content}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
