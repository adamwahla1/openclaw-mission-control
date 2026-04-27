import { useEffect, useState } from 'react'
import {
  DollarSign, Cpu, Clock, Activity
} from 'lucide-react'
import { useCostStore } from '../store/costStore'
import type { CostBreakdownItem } from '../types'

export default function CostDashboard() {
  const { dashboard, loading, fetchDashboard } = useCostStore()
  const [days, setDays] = useState(30)

  useEffect(() => {
    fetchDashboard(days)
  }, [days])

  if (loading && !dashboard) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="animate-spin w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <DollarSign size={20} className="text-emerald-400" />
          <h2 className="text-lg font-semibold">Cost Dashboard</h2>
        </div>
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
          {[7, 14, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 rounded-md text-xs transition ${
                days === d ? 'bg-emerald-500/20 text-emerald-300' : 'text-muted-foreground hover:text-white'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {dashboard ? (
        <div className="flex flex-col gap-6">
          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4">
            <SummaryCard
              icon={<DollarSign size={18} />}
              label="Total Cost"
              value={`$${dashboard.total_cost.toFixed(4)}`}
              color="emerald"
            />
            <SummaryCard
              icon={<Cpu size={18} />}
              label="Total Tokens"
              value={dashboard.total_tokens.toLocaleString()}
              color="blue"
            />
            <SummaryCard
              icon={<Activity size={18} />}
              label="By Agent"
              value={`${dashboard.by_agent.length} agents`}
              color="purple"
            />
            <SummaryCard
              icon={<Clock size={18} />}
              label="Period"
              value={`Last ${dashboard.days} days`}
              color="amber"
            />
          </div>

          {/* Cost by Agent */}
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Cost by Agent</h3>
            {dashboard.by_agent.length > 0 ? (
              <div className="flex flex-col gap-2">
                {dashboard.by_agent.map(item => (
                  <CostBar key={item.label} item={item} max={Math.max(...dashboard.by_agent.map(a => a.total_cost))} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground text-sm">No cost data by agent</div>
            )}
          </div>

          {/* Cost by Model */}
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Cost by Model</h3>
            {dashboard.by_model.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                {dashboard.by_model.map(item => (
                  <div key={item.label} className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{item.label}</span>
                      <span className="text-sm font-semibold text-emerald-300">${item.total_cost.toFixed(4)}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                      <span>{item.record_count} records</span>
                      <span>{item.total_tokens?.toLocaleString() || 0} tokens</span>
                    </div>
                    <div className="h-1.5 bg-white/5 rounded-full mt-2 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full"
                        style={{ width: `${Math.min(100, (item.total_cost / Math.max(...dashboard.by_model.map(m => m.total_cost))) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground text-sm">No cost data by model</div>
            )}
          </div>

          {/* Daily trend */}
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Daily Trend</h3>
            {dashboard.by_day.length > 0 ? (
              <div className="flex items-end gap-1 h-32 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                {dashboard.by_day.slice().reverse().map(item => {
                  const maxCost = Math.max(...dashboard.by_day.map(d => d.total_cost))
                  const height = maxCost > 0 ? (item.total_cost / maxCost) * 100 : 0
                  return (
                    <div key={item.label} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                      <div
                        className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-sm min-h-[2px] opacity-70 hover:opacity-100 transition cursor-pointer"
                        style={{ height: `${Math.max(height, 2)}%` }}
                      />
                      <span className="text-[10px] text-white/30 mt-1">{item.label?.slice(5)}</span>
                      <div className="absolute bottom-full mb-2 bg-black/90 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap z-10">
                        ${item.total_cost.toFixed(4)} · {item.total_tokens?.toLocaleString() || 0} tokens
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground text-sm">No daily cost data</div>
            )}
          </div>

          {/* Recent records */}
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Recent Records</h3>
            {dashboard.recent_records.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                {dashboard.recent_records.map(rec => (
                  <div key={rec.id} className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
                    <div className="flex items-center gap-3">
                      <span className="text-xs px-2 py-0.5 bg-white/5 rounded-full">{rec.model || 'unknown'}</span>
                      <span className="text-sm">{rec.operation || 'general'}</span>
                      {rec.agent_name && <span className="text-xs text-muted-foreground">by {rec.agent_name}</span>}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{rec.total_tokens?.toLocaleString() || 0} tokens</span>
                      <span className="text-emerald-300 font-medium">${rec.cost?.toFixed(4)}</span>
                      <span>{new Date(rec.recorded_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground text-sm">No recent cost records</div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-[60vh] text-center">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
            <DollarSign size={32} className="text-emerald-400/50" />
          </div>
          <p className="text-muted-foreground text-sm">No cost data available</p>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    emerald: 'text-emerald-400 bg-emerald-500/10',
    blue: 'text-blue-400 bg-blue-500/10',
    purple: 'text-purple-400 bg-purple-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
  }
  return (
    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg ${colors[color]}`}>{icon}</div>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  )
}

function CostBar({ item, max }: { item: CostBreakdownItem; max: number }) {
  const pct = max > 0 ? (item.total_cost / max) * 100 : 0
  return (
    <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium truncate">{item.label || 'Unknown'}</span>
        <span className="text-sm font-semibold text-emerald-300">${item.total_cost?.toFixed(4)}</span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
        <span>{item.record_count} records</span>
        <span>{item.total_tokens?.toLocaleString() || 0} tokens</span>
        <span>avg: ${item.avg_cost?.toFixed(4)}</span>
      </div>
    </div>
  )
}
