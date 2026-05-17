import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Cpu,
  Eye,
  EyeOff,
  KeyRound,
  PauseCircle,
  RefreshCw,
  Save,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  TestTube2,
  Wrench,
  XCircle,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface RuntimeStatus {
  active_runtime: string
  ready: boolean
  supervision: string
  runtimes: Array<Record<string, unknown>>
}

interface ProviderConfig {
  provider: string
  display_name: string
  enabled: boolean
  configured: boolean
  api_key_preview?: string
  last_test_status?: string
  last_test_message?: string
}

interface ModelConfig {
  id: string
  purpose: string
  provider: string
  model: string
  routing_policy: string
  temperature: number
  max_tokens: number
  enabled: number | boolean
}

interface ToolConfig {
  id: string
  name: string
  description: string
  risk_level: string
  approval_required: boolean
  enabled: boolean
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

interface RunSummary {
  id: string
  title: string
  status: string
  current_step?: string
}

const routingPolicies = ['auto', 'cheap', 'fast', 'strong', 'pinned']
const runtimeOptions = [
  { id: 'native', label: 'Native Mission Control' },
  { id: 'openclaw', label: 'OpenClaw Adapter' },
]

export default function Settings() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [tools, setTools] = useState<ToolConfig[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [openRouterKey, setOpenRouterKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [savingProvider, setSavingProvider] = useState(false)
  const [testingProvider, setTestingProvider] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const openRouter = providers.find((provider) => provider.provider === 'openrouter')

  const refresh = useCallback(async () => {
    const [runtimeRes, providerRes, modelRes, toolRes, approvalRes, runRes] = await Promise.all([
      fetch('/api/runtime/status'),
      fetch('/api/providers'),
      fetch('/api/model-configs'),
      fetch('/api/tools'),
      fetch('/api/approvals?status=pending'),
      fetch('/api/runs?limit=5'),
    ])
    setRuntime(await runtimeRes.json())
    setProviders(await providerRes.json())
    setModels(await modelRes.json())
    setTools(await toolRes.json())
    setApprovals(await approvalRes.json())
    setRuns(await runRes.json())
  }, [])

  useEffect(() => {
    refresh().catch((e) => setError(String(e)))
  }, [refresh])

  const setActiveRuntime = async (runtimeName: string) => {
    setError(null)
    const res = await fetch('/api/runtime/active', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ runtime: runtimeName }),
    })
    if (!res.ok) throw new Error(await res.text())
    setRuntime(await res.json())
  }

  const saveOpenRouter = async () => {
    setSavingProvider(true)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch('/api/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: 'openrouter',
          display_name: 'OpenRouter',
          enabled: true,
          api_key: openRouterKey || undefined,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      setOpenRouterKey('')
      setNotice('OpenRouter settings saved')
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setSavingProvider(false)
    }
  }

  const testOpenRouter = async () => {
    setTestingProvider(true)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch('/api/providers/openrouter/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: openRouterKey || undefined }),
      })
      const data = await res.json()
      if (!data.ok) throw new Error(data.error || 'OpenRouter test failed')
      setNotice(data.message || 'OpenRouter connected')
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setTestingProvider(false)
    }
  }

  const updateModel = (purpose: string, patch: Partial<ModelConfig>) => {
    setModels((current) => current.map((model) => (model.purpose === purpose ? { ...model, ...patch } : model)))
  }

  const saveModel = async (model: ModelConfig) => {
    setError(null)
    const res = await fetch('/api/model-configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        purpose: model.purpose,
        provider: model.provider || 'openrouter',
        model: model.model,
        routing_policy: model.routing_policy,
        temperature: Number(model.temperature),
        max_tokens: Number(model.max_tokens),
        enabled: Boolean(model.enabled),
      }),
    })
    if (!res.ok) {
      setError(await res.text())
      return
    }
    setNotice(`${model.purpose} model saved`)
    await refresh()
  }

  const patchTool = async (tool: ToolConfig, patch: Partial<ToolConfig>) => {
    const res = await fetch(`/api/tools/${encodeURIComponent(tool.id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!res.ok) {
      setError(await res.text())
      return
    }
    await refresh()
  }

  const decideApproval = async (approval: Approval, decision: 'approve' | 'reject') => {
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
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center">
            <SettingsIcon size={20} className="text-muted-foreground" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Settings</h1>
            <p className="text-sm text-muted-foreground">Runtime, providers, tools, approvals, and model defaults</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw size={14} className="mr-1.5" />
          Refresh
        </Button>
      </div>

      {(notice || error) && (
        <div
          className={cn(
            'flex items-center gap-2 rounded-lg border p-3 text-sm',
            error ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-green-500/30 bg-green-500/10 text-green-300'
          )}
        >
          {error ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{error || notice}</span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu size={18} className="text-muted-foreground" />
              <CardTitle className="text-base">Runtime</CardTitle>
            </div>
            <CardDescription>{runtime?.ready ? 'Ready' : 'Offline'} - {runtime?.supervision ?? 'supervised'}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {runtimeOptions.map((option) => {
                const active = runtime?.active_runtime === option.id
                return (
                  <button
                    key={option.id}
                    onClick={() => setActiveRuntime(option.id).catch((e) => setError(String(e)))}
                    className={cn(
                      'rounded-lg border px-4 py-3 text-left transition-colors',
                      active ? 'border-primary bg-primary/10' : 'hover:bg-accent/50'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-sm">{option.label}</span>
                      {active && <CheckCircle2 size={16} className="text-green-400" />}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{option.id}</div>
                  </button>
                )
              })}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              {(runtime?.runtimes ?? []).map((item) => (
                <div key={String(item.name)} className="rounded-lg border px-3 py-2">
                  <div className="font-medium">{String(item.label ?? item.name)}</div>
                  <div className="text-xs text-muted-foreground mt-1">{String(item.ready ? 'ready' : 'not ready')}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <KeyRound size={18} className="text-muted-foreground" />
              <CardTitle className="text-base">Providers</CardTitle>
            </div>
            <CardDescription>
              OpenRouter {openRouter?.configured ? `configured as ${openRouter.api_key_preview}` : 'not configured'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">OpenRouter API key</label>
              <div className="relative">
                <Input
                  type={showKey ? 'text' : 'password'}
                  value={openRouterKey}
                  onChange={(e) => setOpenRouterKey(e.target.value)}
                  placeholder={openRouter?.configured ? 'Leave blank to keep current key' : 'sk-or-v1-...'}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            {openRouter?.last_test_message && (
              <div className="rounded-lg border px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  {openRouter.last_test_status === 'ok' ? (
                    <CheckCircle2 size={15} className="text-green-400" />
                  ) : (
                    <XCircle size={15} className="text-red-400" />
                  )}
                  <span>{openRouter.last_test_message}</span>
                </div>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button onClick={saveOpenRouter} disabled={savingProvider}>
                {savingProvider ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <Save size={14} className="mr-1.5" />}
                Save
              </Button>
              <Button variant="outline" onClick={testOpenRouter} disabled={testingProvider || (!openRouterKey && !openRouter?.configured)}>
                {testingProvider ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <TestTube2 size={14} className="mr-1.5" />}
                Test
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={18} className="text-muted-foreground" />
            <CardTitle className="text-base">Models</CardTitle>
          </div>
          <CardDescription>Planner, builder, reviewer, fast, and long-context defaults</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {models.map((model) => (
            <div key={model.purpose} className="grid grid-cols-1 lg:grid-cols-[160px_minmax(220px,1fr)_130px_110px_110px_auto] gap-2 items-center rounded-lg border p-3">
              <div>
                <div className="font-medium text-sm">{model.purpose.replace('_', ' ')}</div>
                <div className="text-xs text-muted-foreground">{model.provider}</div>
              </div>
              <Input value={model.model} onChange={(e) => updateModel(model.purpose, { model: e.target.value })} />
              <select
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={model.routing_policy}
                onChange={(e) => updateModel(model.purpose, { routing_policy: e.target.value })}
              >
                {routingPolicies.map((policy) => <option key={policy} value={policy}>{policy}</option>)}
              </select>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="2"
                value={model.temperature}
                onChange={(e) => updateModel(model.purpose, { temperature: Number(e.target.value) })}
              />
              <Input
                type="number"
                min="1"
                value={model.max_tokens}
                onChange={(e) => updateModel(model.purpose, { max_tokens: Number(e.target.value) })}
              />
              <Button variant="outline" size="sm" onClick={() => saveModel(model)}>Save</Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Wrench size={18} className="text-muted-foreground" />
              <CardTitle className="text-base">Tools</CardTitle>
            </div>
            <CardDescription>Risk and approval policy for Project Builder tools</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {tools.map((tool) => (
              <div key={tool.id} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-sm">{tool.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">{tool.description}</div>
                  </div>
                  <span className="rounded-md bg-accent px-2 py-1 text-xs text-muted-foreground">{tool.risk_level}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant={tool.enabled ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => patchTool(tool, { enabled: !tool.enabled })}
                  >
                    {tool.enabled ? 'Enabled' : 'Disabled'}
                  </Button>
                  <Button
                    variant={tool.approval_required ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => patchTool(tool, { approval_required: !tool.approval_required })}
                  >
                    {tool.approval_required ? 'Approval On' : 'Approval Off'}
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-muted-foreground" />
              <CardTitle className="text-base">Approvals</CardTitle>
            </div>
            <CardDescription>{approvals.length} pending decisions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {approvals.length === 0 && <p className="text-sm text-muted-foreground">No pending approvals.</p>}
            {approvals.map((approval) => {
              const draftPreview = approval.request_payload?.draft_preview
              return (
                <div key={approval.id} className="rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 font-medium text-sm">
                        <PauseCircle size={15} className="text-yellow-400" />
                        {approval.tool_name || approval.action_type}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {approval.risk_level || 'read-only'} - {approval.run_id || approval.id}
                      </div>
                    </div>
                    <span className="rounded-md bg-accent px-2 py-1 text-xs text-muted-foreground">{approval.status}</span>
                  </div>
                  {typeof draftPreview === 'string' && (
                    <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted/30 p-3 text-xs text-muted-foreground">
                      {draftPreview}
                    </pre>
                  )}
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={() => decideApproval(approval, 'approve')}>Approve</Button>
                    <Button variant="outline" size="sm" onClick={() => decideApproval(approval, 'reject')}>Reject</Button>
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Runs</CardTitle>
          <CardDescription>Latest native runtime activity</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
            {runs.length === 0 && <p className="text-sm text-muted-foreground">No runs recorded.</p>}
            {runs.map((run) => (
              <div key={run.id} className="rounded-lg border p-3">
                <div className="font-medium text-sm truncate">{run.title}</div>
                <div className="text-xs text-muted-foreground mt-2">{run.status}{run.current_step ? ` - ${run.current_step}` : ''}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
