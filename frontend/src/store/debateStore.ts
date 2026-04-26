import { create } from 'zustand'
import { api } from '@/lib/api'
import type { Debate } from '@/types'

interface DebateStore {
  debates: Debate[]
  currentDebate: Debate | null
  loading: boolean
  error: string | null
  fetchDebates: () => Promise<void>
  setCurrentDebate: (d: Debate | null) => void
  addDebate: (d: Debate) => void
  updateDebate: (id: string, updates: Partial<Debate>) => void
}

export const useDebateStore = create<DebateStore>((set) => ({
  debates: [],
  currentDebate: null,
  loading: false,
  error: null,

  fetchDebates: async () => {
    set({ loading: true, error: null })
    try {
      const debates = await api.get<Debate[]>('/debates')
      set({ debates, loading: false })
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  setCurrentDebate: (d) => set({ currentDebate: d }),

  addDebate: (d) => set((s) => ({ debates: [d, ...s.debates] })),

  updateDebate: (id, updates) =>
    set((s) => ({
      debates: s.debates.map((d) => (d.id === id ? { ...d, ...updates } : d)),
      currentDebate:
        s.currentDebate?.id === id ? { ...s.currentDebate, ...updates } : s.currentDebate,
    })),
}))
