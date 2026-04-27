import { useEffect, useState } from 'react'
import {
  Shield, AlertTriangle, AlertCircle, Info, CheckCircle,
  Search, Scan, Eye, X, Loader2, ChevronDown
} from 'lucide-react'
import { useSecurityStore } from '../store/securityStore'
import type { SecurityAudit } from '../types'

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-300 border-red-500/30',
  warning: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  info: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
}

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  critical: <AlertTriangle size={16} className="text-red-400" />,
  warning: <AlertCircle size={16} className="text-amber-400" />,
  info: <Info size={16} className="text-blue-400" />,
}

export default function SecurityAudit() {
  const { audits, stats, loading, scanning, fetchAudits, fetchStats, scanContent, auditAgent, resolveAudit } = useSecurityStore()
  const [sevFilter, setSevFilter] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('open')
  const [showScan, setShowScan] = useState(false)
  const [showAudit, setShowAudit] = useState(false)
  const [scanForm, setScanForm] = useState({ content: '', content_type: 'general', content_id: '' })
  const [auditAgentId, setAuditAgentId] = useState('')
  const [selectedAudit, setSelectedAudit] = useState<SecurityAudit | null>(null)

  useEffect(() => {
    fetchAudits({ severity: sevFilter || undefined, status: statusFilter || undefined })
    fetchStats()
  }, [sevFilter, statusFilter])

  const handleScan = async () => {
    if (!scanForm.content.trim()) return
    await scanContent(scanForm.content, scanForm.content_type, scanForm.content_id)
    setShowScan(false)
    setScanForm({ content: '', content_type: 'general', content_id: '' })
  }

  const handleAuditAgent = async () => {
    if (!auditAgentId.trim()) return
    await auditAgent(auditAgentId)
    setShowAudit(false)
    setAuditAgentId('')
  }

  return (
    <div className="p-6 h-full flex">
      {/* Left: Audit list */}
      <div className="w-[440px] flex-shrink-0 flex flex-col gap-4 overflow-auto pr-4 border-r border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={20} className="text-blue-400" />
            <h2 className="text-lg font-semibold">Security Audit</h2>
            {stats && <span className={`text-xs px-2 py-0.5 rounded-full ${stats.open_count > 0 ? 'bg-red-500/20 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
              {stats.open_count} open
            </span>}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowScan(true)}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/20 text-blue-300 rounded-lg text-sm hover:bg-blue-500/30 transition"
            >
              <Scan size={14} /> Scan
            </button>
            <button
              onClick={() => setShowAudit(true)}
              className="flex items-center gap-1 px-3 py-1.5 bg-purple-500/20 text-purple-300 rounded-lg text-sm hover:bg-purple-500/30 transition"
            >
              <Eye size={14} /> Audit Agent
            </button>
          </div>
        </div>

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-4 gap-2">
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold text-red-300">{stats.open_count}</div>
              <div className="text-xs text-muted-foreground">Open</div>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold text-emerald-300">{stats.resolved_count}</div>
              <div className="text-xs text-muted-foreground">Resolved</div>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold text-amber-300">{stats.by_severity?.critical || 0}</div>
              <div className="text-xs text-muted-foreground">Critical</div>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold text-blue-300">{stats.by_severity?.warning || 0}</div>
              <div className="text-xs text-muted-foreground">Warnings</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-2">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
          </select>
          <select value={sevFilter} onChange={e => setSevFilter(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-xs focus:outline-none flex-1">
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>

        {/* Severity breakdown bar */}
        {stats && stats.by_severity && (
          <div className="h-2 rounded-full overflow-hidden flex">
            {stats.by_severity.critical > 0 && (
              <div className="bg-red-500" style={{ width: `${(stats.by_severity.critical / stats.total_count) * 100}%` }} />
            )}
            {stats.by_severity.warning > 0 && (
              <div className="bg-amber-500" style={{ width: `${(stats.by_severity.warning / stats.total_count) * 100}%` }} />
            )}
            {stats.by_severity.info > 0 && (
              <div className="bg-blue-500" style={{ width: `${(stats.by_severity.info / stats.total_count) * 100}%` }} />
            )}
          </div>
        )}

        {/* Audit list */}
        {loading && audits.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="animate-spin mr-2" size={16} /> Loading...
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {audits.map(audit => (
              <button
                key={audit.id}
                onClick={() => setSelectedAudit(audit)}
                className={`text-left p-3 rounded-xl border transition hover:border-white/20 ${
                  selectedAudit?.id === audit.id ? 'border-blue-500/50 bg-blue-500/5' : 'border-white/5 bg-white/[0.02]'
                } ${audit.status === 'resolved' ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 flex-shrink-0">{SEVERITY_ICONS[audit.severity]}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm truncate">{audit.title}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[audit.severity]}`}>
                        {audit.severity}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">{audit.description}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-white/30">
                      <span>{audit.audit_type}</span>
                      <span>{audit.target_type}: {audit.target_id?.slice(0, 16)}</span>
                      <span>{new Date(audit.detected_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
            {audits.length === 0 && (
              <div className="text-center py-8 text-muted-foreground text-sm">
                <CheckCircle size={32} className="mx-auto mb-2 text-emerald-500/50" />
                No security findings
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right: Audit detail */}
      <div className="flex-1 pl-6 overflow-auto">
        {selectedAudit ? (
          <AuditDetail audit={selectedAudit} onResolve={(id) => resolveAudit(id, 'operator')} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center mb-4">
              <Shield size={32} className="text-blue-400/50" />
            </div>
            <p className="text-muted-foreground text-sm">Select a finding to view details</p>
          </div>
        )}
      </div>

      {/* Scan modal */}
      {showScan && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowScan(false)}>
          <div className="bg-[#1a1b1e] rounded-2xl p-6 w-[520px] border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Scan Content</h3>
              <button onClick={() => setShowScan(false)} className="text-white/40 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-3">Scan text for leaked secrets and risky patterns</p>
            <div className="flex flex-col gap-3">
              <textarea
                value={scanForm.content}
                onChange={e => setScanForm(f => ({ ...f, content: e.target.value }))}
                placeholder="Paste content to scan..."
                rows={6}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50 resize-none font-mono"
              />
              <div className="flex gap-2">
                <select value={scanForm.content_type} onChange={e => setScanForm(f => ({ ...f, content_type: e.target.value }))} className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  <option value="general">General</option>
                  <option value="code">Code</option>
                  <option value="config">Configuration</option>
                  <option value="log">Log Output</option>
                </select>
                <input value={scanForm.content_id} onChange={e => setScanForm(f => ({ ...f, content_id: e.target.value }))} placeholder="Content ID (optional)" className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowScan(false)} className="px-4 py-2 text-sm text-muted-foreground hover:text-white transition">Cancel</button>
                <button onClick={handleScan} disabled={!scanForm.content.trim() || scanning} className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-400 disabled:opacity-30 transition flex items-center gap-1">
                  {scanning ? <Loader2 size={14} className="animate-spin" /> : <Scan size={14} />} {scanning ? 'Scanning...' : 'Scan'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Audit agent modal */}
      {showAudit && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowAudit(false)}>
          <div className="bg-[#1a1b1e] rounded-2xl p-6 w-[400px] border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Audit Agent</h3>
              <button onClick={() => setShowAudit(false)} className="text-white/40 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-3">Run a full security audit on an agent (config, skills, trust score)</p>
            <input value={auditAgentId} onChange={e => setAuditAgentId(e.target.value)} placeholder="Agent ID" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50 mb-3" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowAudit(false)} className="px-4 py-2 text-sm text-muted-foreground hover:text-white transition">Cancel</button>
              <button onClick={handleAuditAgent} disabled={!auditAgentId.trim()} className="px-4 py-2 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-400 disabled:opacity-30 transition">Run Audit</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AuditDetail({ audit, onResolve }: { audit: SecurityAudit; onResolve: (id: string) => void }) {
  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={`p-2.5 rounded-xl border ${SEVERITY_COLORS[audit.severity]}`}>
            {SEVERITY_ICONS[audit.severity]}
          </div>
          <div>
            <h2 className="text-xl font-semibold">{audit.title}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[audit.severity]}`}>{audit.severity}</span>
              <span className="text-xs text-muted-foreground">{audit.audit_type}</span>
              {audit.status === 'resolved' && (
                <span className="flex items-center gap-1 text-xs text-emerald-300">
                  <CheckCircle size={12} /> Resolved
                </span>
              )}
            </div>
          </div>
        </div>
        {audit.status === 'open' && (
          <button
            onClick={() => onResolve(audit.id)}
            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 text-emerald-300 rounded-lg text-sm hover:bg-emerald-500/30 transition"
          >
            <CheckCircle size={14} /> Resolve
          </button>
        )}
      </div>

      {/* Details */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-xs text-muted-foreground">Target</div>
          <div className="text-sm font-medium mt-0.5">{audit.target_type}: {audit.target_id}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-xs text-muted-foreground">Detected</div>
          <div className="text-sm font-medium mt-0.5">{new Date(audit.detected_at).toLocaleString()}</div>
        </div>
        {audit.resolved_at && (
          <>
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="text-xs text-muted-foreground">Resolved By</div>
              <div className="text-sm font-medium mt-0.5">{audit.resolved_by || 'Unknown'}</div>
            </div>
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="text-xs text-muted-foreground">Resolved At</div>
              <div className="text-sm font-medium mt-0.5">{new Date(audit.resolved_at).toLocaleString()}</div>
            </div>
          </>
        )}
      </div>

      {/* Description */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-2">Description</h3>
        <p className="text-sm leading-relaxed">{audit.description}</p>
      </div>

      {/* Recommendation */}
      <div className="p-4 rounded-xl bg-blue-500/5 border border-blue-500/20">
        <h3 className="text-sm font-medium text-blue-300 mb-1">Recommendation</h3>
        <p className="text-sm">{audit.recommendation}</p>
      </div>

      {/* Metadata */}
      {audit.metadata && Object.keys(audit.metadata).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Metadata</h3>
          <pre className="p-3 rounded-xl bg-black/30 border border-white/5 text-xs font-mono whitespace-pre-wrap text-white/50">
            {JSON.stringify(audit.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
