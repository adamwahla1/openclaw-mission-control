import { useState, useEffect, useCallback } from 'react'
import { Settings as SettingsIcon, Wifi, WifiOff, RefreshCw, Save, Eye, EyeOff, Check, AlertCircle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface GatewaySettings {
  url: string
  token_configured: boolean
  token_preview: string
  source: string
}

interface GatewayDiagnostics {
  connected: boolean
  auth_status: string
  paired: boolean
  pairing_pending: boolean
  auth_error: string | null
  server_info: Record<string, unknown>
  device_auth: {
    device_id: string | null
    has_identity: boolean
    has_operator_token: boolean
    operator_scopes: string[]
    gateway_auth_mode: string
    gateway_url: string
  }
}

export default function Settings() {
  const [gatewayUrl, setGatewayUrl] = useState('')
  const [gatewayToken, setGatewayToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState<GatewaySettings | null>(null)
  const [diagnostics, setDiagnostics] = useState<GatewayDiagnostics | null>(null)
  const [reconnecting, setReconnecting] = useState(false)

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch('/api/gateway/settings')
      const data = await res.json()
      setSettings(data)
      if (!gatewayUrl) setGatewayUrl(data.url)
    } catch {
      // ignore
    }
  }, [gatewayUrl])

  const fetchDiagnostics = useCallback(async () => {
    try {
      const res = await fetch('/api/gateway/status')
      const data = await res.json()
      setDiagnostics(data)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchSettings()
    fetchDiagnostics()
    const interval = setInterval(fetchDiagnostics, 5000)
    return () => clearInterval(interval)
  }, [fetchSettings, fetchDiagnostics])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await fetch('/api/gateway/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: gatewayUrl, token: gatewayToken }),
      })
      const data = await res.json()
      if (data.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
        fetchSettings()
      } else {
        setError(data.error || 'Failed to save settings')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const handleReconnect = async () => {
    setReconnecting(true)
    try {
      await fetch('/api/gateway/reconnect', { method: 'POST' })
      setTimeout(() => {
        fetchDiagnostics()
        setReconnecting(false)
      }, 3000)
    } catch {
      setReconnecting(false)
    }
  }

  const statusColor = diagnostics?.connected
    ? 'text-green-400'
    : diagnostics?.auth_status === 'failed'
      ? 'text-red-400'
      : 'text-yellow-400'

  const statusLabel = diagnostics?.connected
    ? 'Connected'
    : diagnostics?.auth_status === 'failed'
      ? 'Failed'
      : diagnostics?.auth_status === 'challenged' || diagnostics?.auth_status === 'authenticating'
        ? 'Connecting...'
        : 'Disconnected'

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center">
          <SettingsIcon size={20} className="text-muted-foreground" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Settings</h1>
          <p className="text-sm text-muted-foreground">Gateway configuration and system settings</p>
        </div>
      </div>

      {/* Gateway Connection Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {diagnostics?.connected ? (
                <Wifi size={18} className="text-green-400" />
              ) : (
                <WifiOff size={18} className="text-yellow-400" />
              )}
              <CardTitle className="text-base">Gateway Connection</CardTitle>
            </div>
            <span className={`text-sm font-medium ${statusColor}`}>
              {statusLabel}
            </span>
          </div>
          <CardDescription>
            {diagnostics?.server_info?.version
              ? `OpenClaw Gateway v${diagnostics.server_info.version}`
              : 'No gateway connected'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {diagnostics?.auth_error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 text-red-400 text-sm mb-4">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{diagnostics.auth_error}</span>
            </div>
          )}

          {diagnostics?.device_auth && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">Device ID</span>
                <p className="font-mono text-xs mt-0.5 truncate">
                  {diagnostics.device_auth.device_id?.slice(0, 24) || '—'}...
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Auth Status</span>
                <p className="mt-0.5">{diagnostics.auth_status}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Paired</span>
                <p className="mt-0.5">{diagnostics.paired ? '✓ Yes' : 'No'}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Scopes</span>
                <p className="mt-0.5">{diagnostics.device_auth.operator_scopes?.join(', ') || '—'}</p>
              </div>
            </div>
          )}

          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReconnect}
              disabled={reconnecting}
            >
              <RefreshCw size={14} className={reconnecting ? 'animate-spin mr-1.5' : 'mr-1.5'} />
              {reconnecting ? 'Reconnecting...' : 'Reconnect'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Gateway Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Gateway Configuration</CardTitle>
          <CardDescription>
            Connect to a local or remote OpenClaw Gateway. For remote connections, use{' '}
            <code className="text-xs bg-accent px-1 rounded">wss://</code> with your gateway URL.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">
              Gateway URL
            </label>
            <Input
              type="text"
              placeholder="wss://your-machine.tail12345.ts.net:18789"
              value={gatewayUrl}
              onChange={(e) => setGatewayUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Local: <code>ws://127.0.0.1:18789</code> · Remote:{' '}
              <code>wss://your-host:18789</code>
            </p>
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              Gateway Token
            </label>
            <div className="relative">
              <Input
                type={showToken ? 'text' : 'password'}
                placeholder="Enter your gateway authentication token"
                value={gatewayToken}
                onChange={(e) => setGatewayToken(e.target.value)}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {settings?.token_preview && !gatewayToken && (
              <p className="text-xs text-muted-foreground mt-1">
                Current: <code>{settings.token_preview}...</code> (from {settings.source})
              </p>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 text-red-400 text-sm">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button onClick={handleSave} disabled={saving || !gatewayUrl}>
              {saving ? (
                <RefreshCw size={14} className="animate-spin mr-1.5" />
              ) : saved ? (
                <Check size={14} className="mr-1.5" />
              ) : (
                <Save size={14} className="mr-1.5" />
              )}
              {saving ? 'Saving...' : saved ? 'Saved!' : 'Save & Reconnect'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Quick Setup Guide */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Setup Guide</CardTitle>
          <CardDescription>How to connect to your OpenClaw Gateway</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 text-sm">
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-bold">1</span>
              <div>
                <p className="font-medium">Set up OpenClaw locally</p>
                <p className="text-muted-foreground mt-0.5">
                  Install and configure OpenClaw on your machine:{' '}
                  <code className="text-xs bg-accent px-1 rounded">openclaw onboard</code>
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-bold">2</span>
              <div>
                <p className="font-medium">Expose your gateway</p>
                <p className="text-muted-foreground mt-0.5">
                  Use Tailscale Funnel, Cloudflare Tunnel, or port forwarding to expose port 18789.
                  Make sure TLS is enabled for remote connections.
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-bold">3</span>
              <div>
                <p className="font-medium">Get your gateway token</p>
                <p className="text-muted-foreground mt-0.5">
                  Find it in <code className="text-xs bg-accent px-1 rounded">~/.openclaw/openclaw.json</code>{' '}
                  under <code className="text-xs bg-accent px-1 rounded">gateway.auth.token</code>
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-bold">4</span>
              <div>
                <p className="font-medium">Enter URL and token above</p>
                <p className="text-muted-foreground mt-0.5">
                  Paste your gateway URL (e.g. <code className="text-xs bg-accent px-1 rounded">wss://host:18789</code>)
                  and token, then click Save & Reconnect.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
