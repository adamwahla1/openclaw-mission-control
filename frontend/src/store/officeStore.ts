import { create } from 'zustand'
import { api } from '@/lib/api'
import type { OfficeRoom, OfficeAgent, OfficeEvent } from '@/types'

interface OfficeState {
  rooms: OfficeRoom[]
  agents: OfficeAgent[]
  events: OfficeEvent[]
  loading: boolean
  initialized: boolean

  fetchRooms: () => Promise<void>
  fetchPositions: () => Promise<void>
  fetchEvents: () => Promise<void>
  initialize: () => Promise<void>
  simulate: () => Promise<void>
  updatePosition: (agentId: string, data: Partial<OfficeAgent>) => Promise<void>
}

export const useOfficeStore = create<OfficeState>((set, get) => ({
  rooms: [],
  agents: [],
  events: [],
  loading: false,
  initialized: false,

  fetchRooms: async () => {
    try {
      const data = await api.get<OfficeRoom[]>('/office/rooms')
      set({ rooms: data, initialized: data.length > 0 })
    } catch { /* ignore */ }
  },

  fetchPositions: async () => {
    try {
      const data = await api.get<OfficeAgent[]>('/office/positions')
      set({ agents: data })
    } catch { /* ignore */ }
  },

  fetchEvents: async () => {
    try {
      const data = await api.get<OfficeEvent[]>('/office/events')
      set({ events: data })
    } catch { /* ignore */ }
  },

  initialize: async () => {
    set({ loading: true })
    try {
      await api.post('/office/initialize')
      await get().fetchRooms()
      await get().fetchPositions()
      set({ initialized: true })
    } finally {
      set({ loading: false })
    }
  },

  simulate: async () => {
    try {
      await api.post('/office/simulate')
      await Promise.all([get().fetchRooms(), get().fetchPositions()])
    } catch { /* ignore */ }
  },

  updatePosition: async (agentId, data) => {
    try {
      await api.post(`/office/positions/${agentId}`, data)
      await get().fetchPositions()
    } catch { /* ignore */ }
  },
}))
