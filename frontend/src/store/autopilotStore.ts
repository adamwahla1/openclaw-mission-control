import { create } from 'zustand'
import type { AutopilotRun, PipelineTemplate } from '../types'

interface AutopilotState {
  runs: AutopilotRun[]
  templates: Record<string, PipelineTemplate>
  selectedRun: AutopilotRun | null
  loading: boolean
  executing: boolean

  fetchRuns: (status?: string) => Promise<void>
  fetchTemplates: () => Promise<void>
  fetchRun: (id: string) => Promise<void>
  createRun: (data: { name: string; objective: string; template: string; approval_required: boolean }) => Promise<AutopilotRun | null>
  approveRun: (id: string, approvedBy: string) => Promise<void>
  startRun: (id: string) => Promise<void>
  executeStep: (runId: string, stepId: string) => Promise<void>
  completeRun: (id: string) => Promise<void>
  deleteRun: (id: string) => Promise<void>
}

const API = '/api/autopilot'

export const useAutopilotStore = create<AutopilotState>((set, get) => ({
  runs: [],
  templates: {},
  selectedRun: null,
  loading: false,
  executing: false,

  fetchRuns: async (status?: string) => {
    set({ loading: true })
    try {
      const params = status ? `?status=${status}` : ''
      const res = await fetch(`${API}/runs${params}`)
      const runs = await res.json()
      set({ runs, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchTemplates: async () => {
    try {
      const res = await fetch(`${API}/templates`)
      const templates = await res.json()
      set({ templates })
    } catch { /* ignore */ }
  },

  fetchRun: async (id: string) => {
    try {
      const res = await fetch(`${API}/runs/${id}`)
      const run = await res.json()
      set({ selectedRun: run })
    } catch { /* ignore */ }
  },

  createRun: async (data) => {
    try {
      const res = await fetch(`${API}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      const run = await res.json()
      await get().fetchRuns()
      return run
    } catch {
      return null
    }
  },

  approveRun: async (id, approvedBy) => {
    await fetch(`${API}/runs/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved_by: approvedBy }),
    })
    await get().fetchRun(id)
  },

  startRun: async (id) => {
    await fetch(`${API}/runs/${id}/start`, { method: 'POST' })
    await get().fetchRun(id)
  },

  executeStep: async (runId, stepId) => {
    set({ executing: true })
    try {
      await fetch(`${API}/runs/${runId}/execute-step/${stepId}`, { method: 'POST' })
      await get().fetchRun(runId)
    } finally {
      set({ executing: false })
    }
  },

  completeRun: async (id) => {
    await fetch(`${API}/runs/${id}/complete`, { method: 'POST' })
    await get().fetchRun(id)
    await get().fetchRuns()
  },

  deleteRun: async (id) => {
    await fetch(`${API}/runs/${id}`, { method: 'DELETE' })
    set({ selectedRun: null })
    await get().fetchRuns()
  },
}))
