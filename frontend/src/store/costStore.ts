import { create } from 'zustand'
import type { CostDashboard, CostRecord } from '../types'

interface CostState {
  dashboard: CostDashboard | null
  records: CostRecord[]
  loading: boolean

  fetchDashboard: (days?: number) => Promise<void>
  fetchRecords: (filters?: { agent_id?: string; task_id?: string; model?: string }) => Promise<void>
  addRecord: (data: {
    agent_id?: string; task_id?: string; run_id?: string;
    model?: string; operation?: string; input_tokens?: number; output_tokens?: number
  }) => Promise<void>
}

const API = '/api/costs'

export const useCostStore = create<CostState>((set, get) => ({
  dashboard: null,
  records: [],
  loading: false,

  fetchDashboard: async (days = 30) => {
    set({ loading: true })
    try {
      const res = await fetch(`${API}/dashboard?days=${days}`)
      const dashboard = await res.json()
      set({ dashboard, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchRecords: async (filters) => {
    set({ loading: true })
    try {
      const params = new URLSearchParams()
      if (filters?.agent_id) params.set('agent_id', filters.agent_id)
      if (filters?.task_id) params.set('task_id', filters.task_id)
      if (filters?.model) params.set('model', filters.model)
      const qs = params.toString() ? `?${params.toString()}` : ''
      const res = await fetch(`${API}/records${qs}`)
      const records = await res.json()
      set({ records, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  addRecord: async (data) => {
    await fetch(`${API}/records`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    await get().fetchDashboard()
  },
}))
