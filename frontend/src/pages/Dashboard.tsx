import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  KanbanSquare,
  Users,
  Brain,
  Activity,
} from 'lucide-react'

const stats = [
  { label: 'Active Tasks', value: '—', icon: <KanbanSquare size={20} />, color: 'text-blue-500' },
  { label: 'Agents Online', value: '—', icon: <Users size={20} />, color: 'text-green-500' },
  { label: 'Memories', value: '—', icon: <Brain size={20} />, color: 'text-purple-500' },
  { label: 'Events Today', value: '—', icon: <Activity size={20} />, color: 'text-orange-500' },
]

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-2xl font-bold mt-1">{stat.value}</p>
                </div>
                <div className={stat.color}>{stat.icon}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Activity feed placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Activity Feed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
              Connect to OpenClaw Gateway to see live activity
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agent Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
              No agents registered yet
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
