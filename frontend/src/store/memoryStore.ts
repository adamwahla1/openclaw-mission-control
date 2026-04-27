import { create } from 'zustand'
import { api } from '@/lib/api'
import type { Memory, MemoryGraphData, MemoryStats } from '@/types'

interface MemoryState {
  memories: Memory[]
  graphData: MemoryGraphData | null
  stats: MemoryStats | null
  selectedMemory: Memory | null
  loading: boolean
  extractLoading: boolean

  fetchMemories: (params?: Record<string, string | number>) => Promise<void>
  fetchGraphData: (minImportance?: number) => Promise<void>
  fetchStats: () => Promise<void>
  selectMemory: (memory: Memory | null) => void
  createMemory: (data: Partial<Memory> & { content: string }) => Promise<Memory>
  updateMemory: (id: string, data: Partial<Memory>) => Promise<void>
  deleteMemory: (id: string) => Promise<void>
  extractMemories: (sourceText: string, sourceType: string, agentId?: string) => Promise<Memory[]>
  connectMemories: (sourceId: string, targetId: string, type: string, strength: number) => Promise<void>
  applyDecay: () => Promise<void>
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  graphData: null,
  stats: null,
  selectedMemory: null,
  loading: false,
  extractLoading: false,

  fetchMemories: async (params) => {
    set({ loading: true })
    try {
      const query = new URLSearchParams()
      if (params) {
        Object.entries(params).forEach(([k, v]) => query.set(k, String(v)))
      }
      const data = await api.get<Memory[]>(`/memories?${query.toString()}`)
      set({ memories: data })
    } finally {
      set({ loading: false })
    }
  },

  fetchGraphData: async (minImportance = 0) => {
    set({ loading: true })
    try {
      const data = await api.get<MemoryGraphData>(`/memories/graph/data?min_importance=${minImportance}`)
      set({ graphData: data })
    } finally {
      set({ loading: false })
    }
  },

  fetchStats: async () => {
    try {
      const data = await api.get<MemoryStats>('/memories/stats')
      set({ stats: data })
    } catch { /* ignore */ }
  },

  selectMemory: (memory) => set({ selectedMemory: memory }),

  createMemory: async (data) => {
    const memory = await api.post<Memory>('/memories', data)
    set((s) => ({ memories: [memory, ...s.memories] }))
    return memory
  },

  updateMemory: async (id, data) => {
    const updated = await api.patch<Memory>(`/memories/${id}`, data)
    set((s) => ({
      memories: s.memories.map((m) => m.id === id ? updated : m),
      selectedMemory: s.selectedMemory?.id === id ? updated : s.selectedMemory,
    }))
  },

  deleteMemory: async (id) => {
    await api.delete(`/memories/${id}`)
    set((s) => ({
      memories: s.memories.filter((m) => m.id !== id),
      selectedMemory: s.selectedMemory?.id === id ? null : s.selectedMemory,
    }))
  },

  extractMemories: async (sourceText, sourceType, agentId) => {
    set({ extractLoading: true })
    try {
      const body: Record<string, string> = { source_text: sourceText, source_type: sourceType }
      if (agentId) body.agent_id = agentId
      const memories = await api.post<Memory[]>('/memories/extract', body)
      set((s) => ({ memories: [...memories, ...s.memories] }))
      return memories
    } finally {
      set({ extractLoading: false })
    }
  },

  connectMemories: async (sourceId, targetId, type, strength) => {
    await api.post(`/memories/${sourceId}/connections`, {
      target_memory_id: targetId,
      connection_type: type,
      strength,
    })
  },

  applyDecay: async () => {
    await api.post('/memories/decay')
    // Refresh data
    const { fetchGraphData, fetchStats, fetchMemories } = get()
    await Promise.all([fetchGraphData(), fetchStats(), fetchMemories()])
  },
}))
