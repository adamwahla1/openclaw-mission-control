import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Building2, Play, RotateCcw, Users, Activity,
} from 'lucide-react'
import { useOfficeStore } from '@/store/officeStore'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

// ── Constants ────────────────────────────────────────────────────────────────

const ROOM_COLORS: Record<string, string> = {
  control: '#3b82f6',
  desk: '#64748b',
  meeting: '#a855f7',
  creative: '#f59e0b',
  focus: '#22c55e',
  social: '#ec4899',
}

const ROOM_ICONS: Record<string, string> = {
  control: '🖥️',
  desk: '💻',
  meeting: '🤝',
  creative: '💡',
  focus: '🎧',
  social: '☕',
}

const STATE_COLORS: Record<string, string> = {
  idle: '#64748b',
  working: '#3b82f6',
  thinking: '#a855f7',
  collaborating: '#22c55e',
  reviewing: '#f59e0b',
  error: '#ef4444',
}

const STATE_EMOJI: Record<string, string> = {
  idle: '😐',
  working: '💼',
  thinking: '🤔',
  collaborating: '🤝',
  reviewing: '👀',
  error: '⚠️',
}

const FACING_DELTA: Record<string, { dx: number; dy: number }> = {
  down: { dx: 0, dy: 4 },
  up: { dx: 0, dy: -4 },
  left: { dx: -4, dy: 0 },
  right: { dx: 4, dy: 0 },
}

// ── Isometric helpers ────────────────────────────────────────────────────────

function toIso(x: number, y: number): [number, number] {
  return [(x - y) * 0.866, (x + y) * 0.5]
}

// ── Canvas Renderer ──────────────────────────────────────────────────────────

function drawOffice(
  ctx: CanvasRenderingContext2D,
  rooms: any[],
  agents: any[],
  width: number,
  height: number,
  selectedRoom: string | null,
  time: number,
) {
  ctx.clearRect(0, 0, width, height)

  // Background grid
  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 0.5
  for (let x = 0; x < width; x += 40) {
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath()
      ctx.moveTo(x, y)
      ctx.lineTo(x + 40, y)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(x, y)
      ctx.lineTo(x, y + 40)
      ctx.stroke()
    }
  }

  const offsetX = width / 2 - 200
  const offsetY = 100

  // Draw rooms
  for (const room of rooms) {
    const color = ROOM_COLORS[room.room_type] || '#64748b'
    const isSelected = selectedRoom === room.id

    // Isometric floor
    const [x1, y1] = toIso(room.x, room.y)
    const [x2, y2] = toIso(room.x + room.width, room.y)
    const [x3, y3] = toIso(room.x + room.width, room.y + room.height)
    const [x4, y4] = toIso(room.x, room.y + room.height)

    const sx = offsetX
    const sy = offsetY

    // Floor
    ctx.beginPath()
    ctx.moveTo(x1 + sx, y1 + sy)
    ctx.lineTo(x2 + sx, y2 + sy)
    ctx.lineTo(x3 + sx, y3 + sy)
    ctx.lineTo(x4 + sx, y4 + sy)
    ctx.closePath()

    const alpha = isSelected ? 0.3 : 0.15
    ctx.fillStyle = color + Math.round(alpha * 255).toString(16).padStart(2, '0')
    ctx.fill()

    // Border
    ctx.strokeStyle = isSelected ? color : color + '80'
    ctx.lineWidth = isSelected ? 2 : 1
    ctx.stroke()

    // Room label
    const cx = (x1 + x3) / 2 + sx
    const cy = (y1 + y3) / 2 + sy
    ctx.font = `${isSelected ? 'bold ' : ''}11px system-ui`
    ctx.fillStyle = isSelected ? '#ffffff' : '#94a3b8'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(`${ROOM_ICONS[room.room_type] || '🏠'} ${room.name}`, cx, cy - 8)

    // Agent count
    if (room.agents && room.agents.length > 0) {
      ctx.font = '9px system-ui'
      ctx.fillStyle = '#64748b'
      ctx.fillText(`${room.agents.length} agent${room.agents.length > 1 ? 's' : ''}`, cx, cy + 6)
    }

    // Back wall (3D effect)
    const wallH = 20
    ctx.beginPath()
    ctx.moveTo(x1 + sx, y1 + sy)
    ctx.lineTo(x2 + sx, y2 + sy)
    ctx.lineTo(x2 + sx, y2 + sy - wallH)
    ctx.lineTo(x1 + sx, y1 + sy - wallH)
    ctx.closePath()
    ctx.fillStyle = color + '20'
    ctx.fill()
    ctx.strokeStyle = color + '40'
    ctx.lineWidth = 0.5
    ctx.stroke()
  }

  // Draw agents
  for (const agent of agents) {
    if (!agent.room_id) continue

    // Find room for coordinate mapping
    const room = rooms.find((r: any) => r.id === agent.room_id)
    if (!room) continue

    // Agent position in room-local coords → isometric
    const agentWorldX = room.x + (agent.x / room.width) * room.width
    const agentWorldY = room.y + (agent.y / room.height) * room.height
    const [ax, ay] = toIso(agentWorldX, agentWorldY)

    const sx = offsetX
    const sy = offsetY

    const screenX = ax + sx
    const screenY = ay + sy - 4  // lift slightly above floor

    const stateColor = STATE_COLORS[agent.state] || '#64748b'

    // Shadow
    ctx.beginPath()
    ctx.ellipse(screenX, screenY + 4, 8, 3, 0, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(0,0,0,0.3)'
    ctx.fill()

    // Body
    ctx.beginPath()
    ctx.ellipse(screenX, screenY - 6, 7, 10, 0, 0, Math.PI * 2)
    ctx.fillStyle = stateColor + '60'
    ctx.fill()
    ctx.strokeStyle = stateColor
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Head
    ctx.beginPath()
    ctx.arc(screenX, screenY - 18, 5, 0, Math.PI * 2)
    ctx.fillStyle = stateColor + '80'
    ctx.fill()
    ctx.strokeStyle = stateColor
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Emoji on head
    ctx.font = '8px system-ui'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(STATE_EMOJI[agent.state] || '😐', screenX, screenY - 18)

    // Facing direction indicator
    const fd = FACING_DELTA[agent.facing] || FACING_DELTA.down
    ctx.beginPath()
    ctx.moveTo(screenX, screenY - 6)
    ctx.lineTo(screenX + fd.dx * 2, screenY - 6 + fd.dy * 2)
    ctx.strokeStyle = stateColor + '60'
    ctx.lineWidth = 2
    ctx.stroke()

    // Working pulse animation
    if (agent.state === 'working' || agent.state === 'thinking') {
      const pulse = Math.sin(time * 0.003) * 0.5 + 0.5
      ctx.beginPath()
      ctx.ellipse(screenX, screenY - 6, 7 + pulse * 6, 10 + pulse * 6, 0, 0, Math.PI * 2)
      ctx.strokeStyle = stateColor + Math.round(pulse * 80).toString(16).padStart(2, '0')
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // Name label
    ctx.font = '9px system-ui'
    ctx.fillStyle = '#e2e8f0'
    ctx.textAlign = 'center'
    ctx.fillText(agent.name || agent.role, screenX, screenY + 16)
  }
}


// ── Main Component ───────────────────────────────────────────────────────────

export default function VirtualOffice() {
  const {
    rooms, agents, events, loading, initialized,
    fetchRooms, fetchPositions, fetchEvents: _fetchEvents, initialize, simulate,
  } = useOfficeStore()

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animFrameRef = useRef<number>(0)
  const [selectedRoom, setSelectedRoom] = useState<string | null>(null)
  const [simulating, setSimulating] = useState(false)

  useEffect(() => {
    fetchRooms()
    fetchPositions()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-initialize if no rooms
  useEffect(() => {
    if (!initialized && rooms.length === 0 && !loading) {
      initialize()
    }
  }, [initialized, rooms, loading]) // eslint-disable-line react-hooks/exhaustive-deps

  // Canvas animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const resize = () => {
      canvas.width = container.clientWidth * window.devicePixelRatio
      canvas.height = container.clientHeight * window.devicePixelRatio
      canvas.style.width = container.clientWidth + 'px'
      canvas.style.height = container.clientHeight + 'px'
      const ctx = canvas.getContext('2d')
      if (ctx) ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()

    const resizeObs = new ResizeObserver(resize)
    resizeObs.observe(container)

    const animate = (time: number) => {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        const w = container.clientWidth
        const h = container.clientHeight
        drawOffice(ctx, rooms, agents, w, h, selectedRoom, time)
      }
      animFrameRef.current = requestAnimationFrame(animate)
    }
    animFrameRef.current = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(animFrameRef.current)
      resizeObs.disconnect()
    }
  }, [rooms, agents, selectedRoom])

  // Canvas click → select room
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!containerRef.current) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const offsetX = containerRef.current.clientWidth / 2 - 200
    const offsetY = 100

    // Check which room was clicked (reverse iso)
    for (const room of rooms) {
      const [x1, y1] = toIso(room.x, room.y)
      const [x3, y3] = toIso(room.x + room.width, room.y + room.height)
      const cx = (x1 + x3) / 2 + offsetX
      const cy = (y1 + y3) / 2 + offsetY
      const hw = Math.abs(x3 - x1) / 2 + 10
      const hh = Math.abs(y3 - y1) / 2 + 10

      if (Math.abs(x - cx) < hw && Math.abs(y - cy) < hh) {
        setSelectedRoom(selectedRoom === room.id ? null : room.id)
        return
      }
    }
    setSelectedRoom(null)
  }, [rooms, selectedRoom])

  // Simulate with periodic updates
  const handleSimulate = async () => {
    setSimulating(true)
    try {
      // Run 3 simulation steps
      for (let i = 0; i < 3; i++) {
        await simulate()
        await new Promise((r) => setTimeout(r, 800))
      }
    } finally {
      setSimulating(false)
    }
  }

  const selectedRoomData = rooms.find((r) => r.id === selectedRoom)
  const recentEvents = events.slice(0, 10)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Virtual Office</h1>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary">{rooms.length} rooms</Badge>
            <Badge variant="secondary">{agents.length} agents</Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleSimulate} disabled={simulating}>
            {simulating ? (
              <><Activity size={14} className="mr-1 animate-spin" /> Simulating…</>
            ) : (
              <><Play size={14} className="mr-1" /> Simulate Activity</>
            )}
          </Button>
          <Button size="sm" variant="outline" onClick={() => { fetchRooms(); fetchPositions() }}>
            <RotateCcw size={14} className="mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Canvas area */}
        <div className="flex-1 relative" ref={containerRef}>
          {rooms.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center mb-4">
                <Building2 size={32} className="text-muted-foreground" />
              </div>
              <h2 className="text-lg font-semibold mb-1">Office not set up</h2>
              <p className="text-muted-foreground text-sm max-w-sm mb-4">
                Initialize the default office layout to see your agents.
              </p>
              <Button size="sm" onClick={() => initialize()}>
                Initialize Office
              </Button>
            </div>
          ) : (
            <canvas
              ref={canvasRef}
              className="w-full h-full cursor-pointer"
              onClick={handleCanvasClick}
            />
          )}
        </div>

        {/* Right panel */}
        <div className="w-72 shrink-0 border-l border-border overflow-y-auto p-4 space-y-4">
          {/* Selected room info */}
          {selectedRoomData ? (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <span>{ROOM_ICONS[selectedRoomData.room_type] || '🏠'}</span>
                  {selectedRoomData.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Badge variant="secondary" className="capitalize">{selectedRoomData.room_type}</Badge>
                {selectedRoomData.agents && selectedRoomData.agents.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Agents</p>
                    {selectedRoomData.agents.map((agent: any) => (
                      <div key={agent.id} className="flex items-center gap-2 text-xs">
                        <div
                          className="w-6 h-6 rounded-full flex items-center justify-center text-[10px]"
                          style={{ backgroundColor: (STATE_COLORS[agent.state] || '#64748b') + '30', color: STATE_COLORS[agent.state] }}
                        >
                          {STATE_EMOJI[agent.state] || '😐'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">{agent.name}</p>
                          <p className="text-[10px] text-muted-foreground capitalize">{agent.state}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No agents in this room</p>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-6 text-center text-muted-foreground text-xs">
                Click a room on the canvas to see details
              </CardContent>
            </Card>
          )}

          {/* Agent roster */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Users size={14} />
                Agents
                <span className="text-muted-foreground font-normal">({agents.length})</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-60 overflow-y-auto">
              {agents.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-2">No agents positioned</p>
              ) : (
                agents.map((agent) => (
                  <div key={agent.id} className="flex items-center gap-2 text-xs">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0"
                      style={{ backgroundColor: (STATE_COLORS[agent.state] || '#64748b') + '30' }}
                    >
                      {STATE_EMOJI[agent.state] || '😐'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{agent.name}</p>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-muted-foreground capitalize">{agent.state}</span>
                        <span className="text-[10px] text-muted-foreground">·</span>
                        <span className="text-[10px] text-muted-foreground capitalize">{agent.role}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Recent events */}
          {recentEvents.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Activity size={14} />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 max-h-48 overflow-y-auto">
                {recentEvents.map((event) => (
                  <div key={event.id} className="text-xs space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium">{event.agent_name || 'System'}</span>
                      <Badge variant="outline" className="text-[9px] px-1 py-0">{event.event_type}</Badge>
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      {event.data?.to_state ? `→ ${event.data.to_state}` : ''}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Room legend */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Room Types</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {Object.entries(ROOM_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                  <span>{ROOM_ICONS[type]}</span>
                  <span className="capitalize">{type}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
