import { useEffect, useState } from 'react'
import {
  Rocket, Play, CheckCircle, AlertTriangle, Pause, Clock,
  ChevronRight, Plus, Trash2, Shield, Loader2
} from 'lucide-react'
import { useAutopilotStore } from '../store/autopilotStore'
import type { AutopilotRun, AutopilotStepDetail } from '../types'

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-500/20 text-gray-300',
  approved: 'bg-blue-500/20 text-blue-300',
  running: 'bg-amber-500/20 text-amber-300',
  paused: 'bg-orange-500/20 text-orange-300',
  completed: 'bg-emerald-500/20 text-emerald-300',
  failed: 'bg-red-500/20 text-red-300',
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  draft: <Clock size={14} />,
  approved: <CheckCircle size={14} />,
  running: <Play size={14} />,
  paused: <Pause size={14} />,
  completed: <CheckCircle size={14} />,
  failed: <AlertTriangle size={14} />,
}

export default function Autopilot() {
  const { runs, templates, selectedRun, loading, executing, fetchRuns, fetchTemplates, fetchRun, createRun, approveRun, startRun, executeStep, completeRun, deleteRun } = useAutopilotStore()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', objective: '', template: 'feature', approval_required: true })

  useEffect(() => {
    fetchRuns()
    fetchTemplates()
  }, [])

  const handleCreate = async () => {
    if (!form.objective.trim()) return
    await createRun(form)
    setShowCreate(false)
    setForm({ name: '', objective: '', template: 'feature', approval_required: true })
  }

  const handleRunAction = async (run: AutopilotRun) => {
    if (run.status === 'draft') {
      await approveRun(run.id, 'operator')
    } else if (run.status === 'approved') {
      await startRun(run.id)
    }
  }

  const handleExecuteNextStep = async (run: AutopilotRun) => {
    if (!run.step_details) return
    const nextStep = run.step_details.find(s => s.status === 'pending' || s.status === 'in_progress')
    if (nextStep) {
      await executeStep(run.id, nextStep.id)
    }
  }

  return (
    <div className="p-6 h-full flex">
      {/* Left: Run list */}
      <div className="w-96 flex-shrink-0 flex flex-col gap-4 overflow-auto pr-4 border-r border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Rocket size={20} className="text-amber-400" />
            <h2 className="text-lg font-semibold">Autopilot</h2>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-amber-500/20 text-amber-300 rounded-lg text-sm hover:bg-amber-500/30 transition"
          >
            <Plus size={14} /> New Run
          </button>
        </div>

        {/* Pipeline templates */}
        <div className="flex flex-wrap gap-2">
          {Object.entries(templates).map(([key, t]) => (
            <div key={key} className="px-2.5 py-1 bg-white/5 rounded-md text-xs text-muted-foreground">
              {t.name} <span className="text-white/30">({t.steps} steps)</span>
            </div>
          ))}
        </div>

        {loading && runs.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="animate-spin mr-2" size={16} /> Loading...
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground text-sm">
            No autopilot runs yet. Create one to start.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {runs.map(run => (
              <button
                key={run.id}
                onClick={() => fetchRun(run.id)}
                className={`text-left p-3 rounded-xl border transition hover:border-white/20 ${
                  selectedRun?.id === run.id ? 'border-amber-500/50 bg-amber-500/5' : 'border-white/5 bg-white/[0.02]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm truncate flex-1">{run.name || run.id}</span>
                  <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[run.status]}`}>
                    {STATUS_ICONS[run.status]} {run.status}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground truncate">{run.objective}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-white/40">
                  <span>{run.total_steps} steps</span>
                  <span>${run.actual_cost?.toFixed(4) || '0.0000'}</span>
                  <span>{run.tokens_used?.toLocaleString() || 0} tokens</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: Run detail */}
      <div className="flex-1 pl-6 overflow-auto">
        {selectedRun ? (
          <RunDetail
            run={selectedRun}
            executing={executing}
            onAction={handleRunAction}
            onExecuteStep={handleExecuteNextStep}
            onComplete={() => completeRun(selectedRun.id)}
            onDelete={() => deleteRun(selectedRun.id)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 flex items-center justify-center mb-4">
              <Rocket size={32} className="text-amber-400/50" />
            </div>
            <p className="text-muted-foreground text-sm">Select a run to view details</p>
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-[#1a1b1e] rounded-2xl p-6 w-[480px] border border-white/10" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">New Autopilot Run</h3>
            <div className="flex flex-col gap-3">
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Run name (optional)"
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/50"
              />
              <textarea
                value={form.objective}
                onChange={e => setForm(f => ({ ...f, objective: e.target.value }))}
                placeholder="What should the autopilot accomplish?"
                rows={3}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/50 resize-none"
              />
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Pipeline Template</label>
                <select
                  value={form.template}
                  onChange={e => setForm(f => ({ ...f, template: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none"
                >
                  {Object.entries(templates).map(([key, t]) => (
                    <option key={key} value={key}>{t.name} ({t.steps} steps)</option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.approval_required}
                  onChange={e => setForm(f => ({ ...f, approval_required: e.target.checked }))}
                  className="rounded"
                />
                <Shield size={14} /> Requires approval before execution
              </label>
              <div className="flex justify-end gap-2 mt-2">
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-muted-foreground hover:text-white transition">Cancel</button>
                <button
                  onClick={handleCreate}
                  disabled={!form.objective.trim()}
                  className="px-4 py-2 bg-amber-500 text-black rounded-lg text-sm font-medium hover:bg-amber-400 disabled:opacity-30 transition"
                >
                  Create Run
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RunDetail({ run, executing, onAction, onExecuteStep, onComplete, onDelete }: {
  run: AutopilotRun
  executing: boolean
  onAction: (run: AutopilotRun) => void
  onExecuteStep: (run: AutopilotRun) => void
  onComplete: () => void
  onDelete: () => void
}) {
  const steps = run.step_details || []
  const completedSteps = steps.filter(s => s.status === 'completed').length
  const progress = steps.length > 0 ? (completedSteps / steps.length) * 100 : 0
  const pendingStep = steps.find(s => s.status === 'pending' || s.status === 'in_progress')

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold">{run.name || run.id}</h2>
          <p className="text-muted-foreground text-sm mt-1">{run.objective}</p>
        </div>
        <div className="flex items-center gap-2">
          {run.status === 'draft' && (
            <button onClick={() => onAction(run)} className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/20 text-blue-300 rounded-lg text-sm hover:bg-blue-500/30 transition">
              <CheckCircle size={14} /> Approve
            </button>
          )}
          {run.status === 'approved' && (
            <button onClick={() => onAction(run)} className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 text-emerald-300 rounded-lg text-sm hover:bg-emerald-500/30 transition">
              <Play size={14} /> Start
            </button>
          )}
          {run.status === 'running' && pendingStep && (
            <button
              onClick={() => onExecuteStep(run)}
              disabled={executing}
              className="flex items-center gap-1 px-3 py-1.5 bg-amber-500/20 text-amber-300 rounded-lg text-sm hover:bg-amber-500/30 transition disabled:opacity-50"
            >
              {executing ? <Loader2 size={14} className="animate-spin" /> : <ChevronRight size={14} />}
              {executing ? 'Executing...' : `Execute: ${pendingStep.name}`}
            </button>
          )}
          {run.status === 'running' && !pendingStep && (
            <button onClick={onComplete} className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 text-emerald-300 rounded-lg text-sm hover:bg-emerald-500/30 transition">
              <CheckCircle size={14} /> Complete
            </button>
          )}
          <button onClick={onDelete} className="p-1.5 text-red-400/50 hover:text-red-400 transition">
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-4">
        <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[run.status]}`}>
          {STATUS_ICONS[run.status]} {run.status.toUpperCase()}
        </span>
        <span className="text-sm text-muted-foreground">{completedSteps}/{steps.length} steps</span>
        <span className="text-sm text-muted-foreground">${run.actual_cost?.toFixed(4) || '0.0000'}</span>
        <span className="text-sm text-muted-foreground">{run.tokens_used?.toLocaleString() || 0} tokens</span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber-500 to-emerald-500 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Pipeline steps */}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">Pipeline Steps</h3>
        {steps.map((step, i) => (
          <StepCard key={step.id} step={step} index={i} isLast={i === steps.length - 1} />
        ))}
      </div>

      {/* Quality gates */}
      {run.quality_gates && run.quality_gates.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">Quality Gates</h3>
          {run.quality_gates.map((gate, i) => (
            <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="flex items-center gap-2">
                <Shield size={14} className="text-blue-400" />
                <span className="text-sm">After step {gate.after_step + 1}: {gate.check}</span>
              </div>
              <span className="text-xs text-muted-foreground">threshold: {gate.threshold}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StepCard({ step, index: _index, isLast }: { step: AutopilotStepDetail; index: number; isLast: boolean }) {
  const STEP_TYPE_COLORS: Record<string, string> = {
    research: 'text-blue-400 bg-blue-500/10',
    plan: 'text-purple-400 bg-purple-500/10',
    execute: 'text-amber-400 bg-amber-500/10',
    review: 'text-cyan-400 bg-cyan-500/10',
    validate: 'text-emerald-400 bg-emerald-500/10',
    deploy: 'text-green-400 bg-green-500/10',
    report: 'text-pink-400 bg-pink-500/10',
  }
  const STEP_ICONS: Record<string, string> = {
    research: '🔍', plan: '📋', execute: '⚡', review: '🔎',
    validate: '✅', deploy: '🚀', report: '📊',
  }

  const color = STEP_TYPE_COLORS[step.step_type] || 'text-gray-400 bg-gray-500/10'

  return (
    <div className={`relative ${!isLast ? 'pb-2' : ''}`}>
      {!isLast && (
        <div className="absolute left-5 top-10 bottom-0 w-px bg-white/10" />
      )}
      <div className={`flex items-start gap-3 p-3 rounded-xl border transition ${
        step.status === 'completed' ? 'border-emerald-500/20 bg-emerald-500/5' :
        step.status === 'in_progress' ? 'border-amber-500/20 bg-amber-500/5' :
        step.status === 'failed' ? 'border-red-500/20 bg-red-500/5' :
        'border-white/5 bg-white/[0.02]'
      }`}>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0 ${color}`}>
          {step.status === 'in_progress' ? <Loader2 size={18} className="animate-spin" /> : STEP_ICONS[step.step_type] || '⚙️'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="font-medium text-sm">{step.name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-300' :
              step.status === 'in_progress' ? 'bg-amber-500/20 text-amber-300' :
              step.status === 'failed' ? 'bg-red-500/20 text-red-300' :
              'bg-white/5 text-white/40'
            }`}>
              {step.status}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
          {step.quality_score !== null && step.quality_score > 0 && (
            <div className="flex items-center gap-2 mt-1">
              <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${step.quality_score >= 0.8 ? 'bg-emerald-500' : step.quality_score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${step.quality_score * 100}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground">Q: {step.quality_score.toFixed(2)}</span>
            </div>
          )}
          {step.gate_result && (
            <div className={`mt-1 text-xs px-2 py-0.5 rounded ${
              Array.isArray(step.gate_result)
                ? step.gate_result.some((g: any) => !g.passed) ? 'bg-red-500/10 text-red-300' : 'bg-emerald-500/10 text-emerald-300'
                : 'bg-white/5 text-muted-foreground'
            }`}>
              {Array.isArray(step.gate_result)
                ? step.gate_result.map((g: any) => g.message).join(' | ')
                : JSON.stringify(step.gate_result)
              }
            </div>
          )}
          {step.tokens_used > 0 && (
            <span className="text-xs text-white/30 mt-1 block">{step.tokens_used.toLocaleString()} tokens · ${step.cost?.toFixed(4)}</span>
          )}
        </div>
      </div>
    </div>
  )
}
