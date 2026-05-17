import { useState, useEffect } from 'react'

interface GatewayStatus {
  connected: boolean
  auth: string
  server: Record<string, unknown> | null
}

export function useGatewayStatus(pollMs = 5000): GatewayStatus {
  const [status, setStatus] = useState<GatewayStatus>({
    connected: false,
    auth: 'none',
    server: null,
  })

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/runtime/status')
        const data = await res.json()
        setStatus({
          connected: data.ready ?? false,
          auth: data.active_runtime ?? 'native',
          server: data,
        })
      } catch {
        setStatus((s) => ({ ...s, connected: false }))
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, pollMs)
    return () => clearInterval(interval)
  }, [pollMs])

  useEffect(() => {
    const es = new EventSource('/events')

    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setStatus((current) => ({
          connected: data.status === 'ready' || data.status === 'active_changed' ? true : current.connected,
          auth: data.active_runtime ?? current.auth,
          server: { ...(current.server ?? {}), ...data },
        }))
      } catch {
        // ignore malformed events
      }
    }

    es.addEventListener('runtime', handler)
    return () => es.close()
  }, [])

  return status
}
