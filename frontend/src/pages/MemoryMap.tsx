import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'
import {
  Brain, Plus, Search, Filter, Clock, Sparkles, Trash2, Link2,
  ChevronDown, AlertCircle, Activity,
} from 'lucide-react'
import { useMemoryStore } from '@/store/memoryStore'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import type { Memory, MemoryGraphNode, MemoryGraphLink } from '@/types'

// ── Constants ────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  fact: '#3b82f6',         // blue
  insight: '#a855f7',      // purple
  procedure: '#22c55e',    // green
  experience: '#f59e0b',   // amber
  preference: '#ec4899',   // pink
}

const TYPE_ICONS: Record<string, string> = {
  fact: '📋',
  insight: '💡',
  procedure: '⚙️',
  experience: '🎯',
  preference: '❤️',
}

const LINK_COLORS: Record<string, string> = {
  related: '#475569',
  causes: '#f59e0b',
  contradicts: '#ef4444',
  supports: '#22c55e',
  derives: '#3b82f6',
}

// ── D3 Node/Link types ──────────────────────────────────────────────────────

interface SimNode extends d3.SimulationNodeDatum, MemoryGraphNode {
  // D3 adds x, y, vx, vy
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  connection_type: string
  strength: number
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function MemoryMap() {
  const {
    graphData, stats, selectedMemory, loading,
    fetchGraphData, fetchStats, selectMemory,
    createMemory, deleteMemory, extractMemories, applyDecay,
  } = useMemoryStore()

  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [minImportance, setMinImportance] = useState(0.3)
  const [searchQuery, setSearchQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [extractOpen, setExtractOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    fetchGraphData(minImportance)
    fetchStats()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch when filter changes
  const handleFilterChange = useCallback((val: number) => {
    setMinImportance(val)
    fetchGraphData(val)
  }, [fetchGraphData])

  // ── D3 Force Graph ──────────────────────────────────────────────────────

  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return

    const container = containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    // Build nodes and links
    const nodes: SimNode[] = graphData.nodes.map((n) => ({ ...n }))
    const links: SimLink[] = graphData.links.map((l) => ({
      source: l.source_memory_id,
      target: l.target_memory_id,
      connection_type: l.connection_type,
      strength: l.strength,
    }))

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    const g = svg.append('g')

    // Force simulation
    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((d) => 120 - d.strength * 60)
      )
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(35))

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) => LINK_COLORS[d.connection_type] || '#475569')
      .attr('stroke-opacity', (d) => 0.3 + d.strength * 0.5)
      .attr('stroke-width', (d) => 1 + d.strength * 2)
      .attr('stroke-dasharray', (d) => d.connection_type === 'contradicts' ? '4,4' : 'none')

    // Link labels
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(links)
      .join('text')
      .text((d) => d.connection_type)
      .attr('font-size', 8)
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .attr('dy', -3)

    // Node groups
    const node = g.append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .call(d3.drag<SVGGElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )

    // Node circles with glow
    const defs = svg.append('defs')
    nodes.forEach((d) => {
      const color = TYPE_COLORS[d.memory_type] || '#64748b'
      const filterId = `glow-${d.id.slice(0, 8)}`
      const filter = defs.append('filter').attr('id', filterId)
      filter.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'blur')
      filter.append('feMerge')
        .selectAll('feMergeNode')
        .data(['blur', 'SourceGraphic'])
        .join('feMergeNode')
        .attr('in', (d) => d)
    })

    // Outer glow ring (decay indicator)
    node.append('circle')
      .attr('r', (d) => 8 + d.importance * 14)
      .attr('fill', 'none')
      .attr('stroke', (d) => TYPE_COLORS[d.memory_type] || '#64748b')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', (d) => d.decay_score * 0.6)

    // Main circle
    node.append('circle')
      .attr('r', (d) => 6 + d.importance * 10)
      .attr('fill', (d) => TYPE_COLORS[d.memory_type] || '#64748b')
      .attr('fill-opacity', (d) => 0.3 + d.decay_score * 0.5)
      .attr('stroke', (d) => TYPE_COLORS[d.memory_type] || '#64748b')
      .attr('stroke-width', 2)

    // Icon/emoji in center
    node.append('text')
      .text((d) => TYPE_ICONS[d.memory_type] || '📝')
      .attr('text-anchor', 'middle')
      .attr('dy', 1)
      .attr('font-size', (d) => 8 + d.importance * 4)
      .style('pointer-events', 'none')

    // Label below
    node.append('text')
      .text((d) => d.content.slice(0, 30) + (d.content.length > 30 ? '…' : ''))
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => 16 + d.importance * 10)
      .attr('font-size', 9)
      .attr('fill', '#94a3b8')
      .style('pointer-events', 'none')

    // Hover tooltip
    node.on('click', (event, d) => {
      event.stopPropagation()
      // Fetch full memory detail
      api.get<Memory>(`/memories/${d.id}`).then(selectMemory).then(() => setDetailOpen(true))
    })

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!)

      linkLabel
        .attr('x', (d) => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', (d) => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    // Click background to deselect
    svg.on('click', () => {
      selectMemory(null)
      setDetailOpen(false)
    })

    return () => {
      simulation.stop()
    }
  }, [graphData]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Memory Map</h1>
          {stats && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary">{stats.total} memories</Badge>
              <Badge variant="secondary">{stats.connections} links</Badge>
              <Badge variant="outline">avg decay: {(stats.avg_decay * 100).toFixed(0)}%</Badge>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => applyDecay()}>
            <Clock size={14} className="mr-1" />
            Decay
          </Button>
          <Button size="sm" variant="outline" onClick={() => setExtractOpen(true)}>
            <Sparkles size={14} className="mr-1" />
            Extract
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus size={14} className="mr-1" />
            Add Memory
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Graph area */}
        <div className="flex-1 relative" ref={containerRef}>
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Activity size={16} className="animate-spin" />
                Loading graph…
              </div>
            </div>
          )}

          {(!graphData || graphData.nodes.length === 0) && !loading ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center mb-4">
                <Brain size={32} className="text-muted-foreground" />
              </div>
              <h2 className="text-lg font-semibold mb-1">No memories yet</h2>
              <p className="text-muted-foreground text-sm max-w-sm mb-4">
                Add memories manually or extract them from task reports and debates.
              </p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setExtractOpen(true)}>
                  <Sparkles size={14} className="mr-1" />
                  Extract from Text
                </Button>
                <Button size="sm" onClick={() => setCreateOpen(true)}>
                  <Plus size={14} className="mr-1" />
                  Add Memory
                </Button>
              </div>
            </div>
          ) : (
            <svg ref={svgRef} className="w-full h-full" />
          )}

          {/* Legend */}
          {graphData && graphData.nodes.length > 0 && (
            <div className="absolute bottom-4 left-4 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-3 space-y-1.5">
              <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">Types</p>
              {Object.entries(TYPE_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                  <span className="capitalize">{type}</span>
                  <span className="text-muted-foreground">
                    ({TYPE_ICONS[type]})
                  </span>
                </div>
              ))}
              <div className="border-t border-border pt-1.5 mt-1.5">
                <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">Links</p>
                {Object.entries(LINK_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2 text-xs">
                    <div className="w-5 h-0.5" style={{ backgroundColor: color }} />
                    <span className="capitalize">{type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Importance filter */}
          <div className="absolute top-4 left-4 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-3 w-48">
            <label className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider block mb-1">
              Min Importance: {minImportance.toFixed(1)}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={minImportance}
              onChange={(e) => handleFilterChange(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
        </div>

        {/* Right panel — memory detail */}
        {selectedMemory && detailOpen && (
          <div className="w-80 shrink-0 border-l border-border overflow-y-auto p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Memory Detail</h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => { selectMemory(null); setDetailOpen(false) }}
              >
                ✕
              </Button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Content</label>
                <p className="text-sm mt-1">{selectedMemory.content}</p>
              </div>

              <div className="flex gap-2 flex-wrap">
                <Badge style={{ backgroundColor: TYPE_COLORS[selectedMemory.memory_type] + '20', color: TYPE_COLORS[selectedMemory.memory_type] }}>
                  {TYPE_ICONS[selectedMemory.memory_type]} {selectedMemory.memory_type}
                </Badge>
                <Badge variant="secondary">{selectedMemory.category}</Badge>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-secondary rounded-lg p-2">
                  <p className="text-muted-foreground">Importance</p>
                  <p className="font-medium">{(selectedMemory.importance * 100).toFixed(0)}%</p>
                </div>
                <div className="bg-secondary rounded-lg p-2">
                  <p className="text-muted-foreground">Decay</p>
                  <p className="font-medium">{(selectedMemory.decay_score * 100).toFixed(0)}%</p>
                </div>
                <div className="bg-secondary rounded-lg p-2">
                  <p className="text-muted-foreground">Accessed</p>
                  <p className="font-medium">{selectedMemory.access_count}×</p>
                </div>
                <div className="bg-secondary rounded-lg p-2">
                  <p className="text-muted-foreground">Source</p>
                  <p className="font-medium capitalize">{selectedMemory.source || 'manual'}</p>
                </div>
              </div>

              {selectedMemory.tags && selectedMemory.tags.length > 0 && (
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Tags</label>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {selectedMemory.tags.map((tag) => (
                      <Badge key={tag} variant="outline" className="text-[10px]">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {selectedMemory.outgoing_connections && selectedMemory.outgoing_connections.length > 0 && (
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Connections</label>
                  <div className="space-y-1 mt-1">
                    {selectedMemory.outgoing_connections.map((conn) => (
                      <div key={conn.id} className="flex items-center gap-1.5 text-xs bg-secondary rounded p-1.5">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: LINK_COLORS[conn.connection_type] }} />
                        <span className="capitalize text-muted-foreground">{conn.connection_type}</span>
                        <span className="truncate">{conn.target_content?.slice(0, 30)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Button
                variant="destructive"
                size="sm"
                className="w-full"
                onClick={async () => {
                  await deleteMemory(selectedMemory.id)
                  setDetailOpen(false)
                  fetchGraphData(minImportance)
                }}
              >
                <Trash2 size={14} className="mr-1" />
                Delete Memory
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Create memory dialog */}
      <CreateMemoryDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => { fetchGraphData(minImportance); fetchStats() }}
      />

      {/* Extract memories dialog */}
      <ExtractMemoryDialog
        open={extractOpen}
        onClose={() => setExtractOpen(false)}
        onExtracted={() => { fetchGraphData(minImportance); fetchStats() }}
      />
    </div>
  )
}


// ── Create Memory Dialog ─────────────────────────────────────────────────────

function CreateMemoryDialog({
  open, onClose, onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => void
}) {
  const { createMemory } = useMemoryStore()
  const [content, setContent] = useState('')
  const [memoryType, setMemoryType] = useState('fact')
  const [category, setCategory] = useState('general')
  const [importance, setImportance] = useState('0.5')
  const [tags, setTags] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setContent(''); setMemoryType('fact'); setCategory('general')
    setImportance('0.5'); setTags(''); setSubmitting(false)
  }
  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    try {
      await createMemory({
        content: content.trim(),
        memory_type: memoryType as Memory['memory_type'],
        category,
        importance: Number(importance),
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      })
      onCreated()
      handleClose()
    } catch { /* ignore */ }
    finally { setSubmitting(false) }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Memory</DialogTitle>
          </DialogHeader>
          <div className="px-6 space-y-4">
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Content</label>
              <Textarea
                autoFocus
                placeholder="What should be remembered?"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={3}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Type</label>
                <Select value={memoryType} onChange={(e) => setMemoryType(e.target.value)}>
                  <option value="fact">📋 Fact</option>
                  <option value="insight">💡 Insight</option>
                  <option value="procedure">⚙️ Procedure</option>
                  <option value="experience">🎯 Experience</option>
                  <option value="preference">❤️ Preference</option>
                </Select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Category</label>
                <Input
                  placeholder="e.g., technical"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">
                Importance: {Number(importance).toFixed(1)}
              </label>
              <input
                type="range" min="0" max="1" step="0.1"
                value={importance}
                onChange={(e) => setImportance(e.target.value)}
                className="w-full accent-primary"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Tags (comma-separated)</label>
              <Input
                placeholder="e.g., api, performance"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={submitting || !content.trim()}>
              {submitting ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}


// ── Extract Memories Dialog ──────────────────────────────────────────────────

function ExtractMemoryDialog({
  open, onClose, onExtracted,
}: {
  open: boolean
  onClose: () => void
  onExtracted: () => void
}) {
  const { extractMemories, extractLoading } = useMemoryStore()
  const [sourceText, setSourceText] = useState('')
  const [sourceType, setSourceType] = useState('report')
  const [error, setError] = useState<string | null>(null)

  const reset = () => { setSourceText(''); setSourceType('report'); setError(null) }
  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sourceText.trim()) return
    setError(null)
    try {
      const memories = await extractMemories(sourceText.trim(), sourceType)
      if (memories.length > 0) {
        onExtracted()
        handleClose()
      }
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Extract Memories</DialogTitle>
          </DialogHeader>
          <div className="px-6 space-y-4">
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Source Text</label>
              <Textarea
                autoFocus
                placeholder="Paste a report, debate transcript, or document to extract memories from…"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                rows={8}
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Source Type</label>
              <Select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                <option value="report">Task Report</option>
                <option value="debate">Debate Transcript</option>
                <option value="conversation">Conversation</option>
                <option value="document">Document</option>
              </Select>
            </div>
            {error && (
              <div className="flex items-center gap-2 text-destructive text-xs">
                <AlertCircle size={14} />
                {error}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={extractLoading || !sourceText.trim()}>
              {extractLoading ? (
                <><Sparkles size={14} className="mr-1 animate-spin" /> Extracting…</>
              ) : (
                <><Sparkles size={14} className="mr-1" /> Extract with AI</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
