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

  // 1. Poll for initial state (also catches SSE dropouts)
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/gateway/status')
        const data = await res.json()
        setStatus({
          connected: data.connected ?? false,
          auth: data.server?.auth ?? 'none',
          server: data.server ?? null,
        })
      } catch {
        setStatus((s) => ({ ...s, connected: false }))
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, pollMs)
    return () => clearInterval(interval)
  }, [pollMs])

  // 2. Listen to SSE for instant updates
  useEffect(() => {
    const es = new EventSource('/events')

    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        if (data.status === 'connected') {
          setStatus({
            connected: true,
            auth: data.auth ?? 'authenticated',
            server: data.server ?? null,
          })
        } else if (data.status === 'disconnected') {
          setStatus({ connected: false, auth: 'none', server: null })
        }
      } catch {
        // ignore
      }
    }

    es.addEventListener('gateway', handler)
    return () => es.close()
  }, [])

  return status
}
