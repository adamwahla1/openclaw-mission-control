import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, CheckCircle2, Clock, PauseCircle, RefreshCw, Square, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
  const [loading, setLoading] = useState(false)

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? runs[0] ?? null,
    [runs, selectedId]
  )

  const fetchRuns = useCallback(async () => {
    const res = await fetch('/api/runs?limit=50')
    const data = await res.json()
    setRuns(data)
    setSelectedId((current) => current ?? data[0]?.id ?? null)
  }, [])

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
    fetchRuns()
  }, [fetchRuns])

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
        fetchRuns()
      } catch {
        // ignore malformed events
      }
    }
    es.addEventListener('run.event', handler)
    return () => es.close()
  }, [selectedRun?.id, fetchRuns])

  const cancelRun = async () => {
    if (!selectedRun) return
    await fetch(`/api/runs/${selectedRun.id}/cancel`, { method: 'POST' })
    await fetchRuns()
    await fetchEvents(selectedRun.id)
  }

  const resumeRun = async () => {
    if (!selectedRun) return
    await fetch(`/api/runs/${selectedRun.id}/resume`, { method: 'POST' })
    await fetchRuns()
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
            <p className="text-sm text-muted-foreground">Native runtime trace and approval timeline</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={fetchRuns}>
          <RefreshCw size={14} className="mr-1.5" />
          Refresh
        </Button>
      </div>

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
