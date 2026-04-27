import { create } from 'zustand'
import type { SecurityAudit, SecurityStats, AgentAuditResult } from '../types'

interface SecurityState {
  audits: SecurityAudit[]
  stats: SecurityStats | null
  loading: boolean
  scanning: boolean

  fetchAudits: (filters?: { severity?: string; status?: string; target_type?: string }) => Promise<void>
  fetchStats: () => Promise<void>
  scanContent: (content: string, contentType?: string, contentId?: string) => Promise<SecurityAudit[]>
  auditAgent: (agentId: string) => Promise<AgentAuditResult | null>
  resolveAudit: (auditId: string, resolvedBy: string) => Promise<void>
}

const API = '/api/security'

export const useSecurityStore = create<SecurityState>((set, get) => ({
  audits: [],
  stats: null,
  loading: false,
  scanning: false,

  fetchAudits: async (filters) => {
    set({ loading: true })
    try {
      const params = new URLSearchParams()
      if (filters?.severity) params.set('severity', filters.severity)
      if (filters?.status) params.set('status', filters.status)
      if (filters?.target_type) params.set('target_type', filters.target_type)
      const qs = params.toString() ? `?${params}` : ''
      const res = await fetch(`${API}/audits${qs}`)
      const audits = await res.json()
      set({ audits, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchStats: async () => {
    try {
      const res = await fetch(`${API}/stats`)
      const stats = await res.json()
      set({ stats })
    } catch { /* ignore */ }
  },

  scanContent: async (content, contentType = 'general', contentId = '') => {
    set({ scanning: true })
    try {
      const res = await fetch(`${API}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, content_type: contentType, content_id: contentId }),
      })
      const result = await res.json()
      await get().fetchAudits()
      await get().fetchStats()
      return result.findings || []
    } catch {
      return []
    } finally {
      set({ scanning: false })
    }
  },

  auditAgent: async (agentId) => {
    try {
      const res = await fetch(`${API}/audit-agent/${agentId}`, { method: 'POST' })
      const result = await res.json()
      await get().fetchAudits()
      await get().fetchStats()
      return result
    } catch {
      return null
    }
  },

  resolveAudit: async (auditId, resolvedBy) => {
    await fetch(`${API}/resolve/${auditId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolved_by: resolvedBy }),
    })
    await get().fetchAudits()
    await get().fetchStats()
  },
}))
