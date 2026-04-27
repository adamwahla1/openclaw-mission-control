import { create } from 'zustand'
import type { Skill, SkillStats } from '../types'

interface SkillsState {
  skills: Skill[]
  stats: SkillStats | null
  selectedSkill: Skill | null
  categories: { category: string; count: number }[]
  loading: boolean
  // Registry browser
  registryResults: any[]
  registryStats: Record<string, any>
  registryLoading: boolean

  fetchSkills: (category?: string, skill_type?: string) => Promise<void>
  fetchStats: () => Promise<void>
  fetchCategories: () => Promise<void>
  fetchSkill: (id: string) => Promise<void>
  createSkill: (data: {
    name: string; description?: string; category?: string; skill_type?: string;
    prompt_template?: string; tags?: string[]
  }) => Promise<string | null>
  updateSkill: (id: string, data: Partial<Skill>) => Promise<void>
  deleteSkill: (id: string) => Promise<void>
  bindSkill: (agentId: string, skillId: string, confidence?: number) => Promise<void>
  unbindSkill: (agentId: string, skillId: string) => Promise<void>
  searchRegistries: (query?: string, registry?: string, category?: string) => Promise<void>
  fetchRegistryStats: () => Promise<void>
  installFromRegistry: (name: string, registry: string, category?: string) => Promise<{ status: string; id?: string } | null>
}

const API = '/api/skills'

export const useSkillsStore = create<SkillsState>((set, get) => ({
  skills: [],
  stats: null,
  selectedSkill: null,
  categories: [],
  loading: false,
  registryResults: [],
  registryStats: {},
  registryLoading: false,

  fetchSkills: async (category?: string, skill_type?: string) => {
    set({ loading: true })
    try {
      const params = new URLSearchParams()
      if (category) params.set('category', category)
      if (skill_type) params.set('skill_type', skill_type)
      const qs = params.toString() ? `?${params}` : ''
      const res = await fetch(`${API}${qs}`)
      const skills = await res.json()
      set({ skills, loading: false })
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

  fetchCategories: async () => {
    try {
      const res = await fetch(`${API}/categories`)
      const categories = await res.json()
      set({ categories })
    } catch { /* ignore */ }
  },

  fetchSkill: async (id) => {
    try {
      const res = await fetch(`${API}/${id}`)
      const skill = await res.json()
      set({ selectedSkill: skill })
    } catch { /* ignore */ }
  },

  createSkill: async (data) => {
    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      const result = await res.json()
      await get().fetchSkills()
      await get().fetchStats()
      return result.id
    } catch {
      return null
    }
  },

  updateSkill: async (id, data) => {
    await fetch(`${API}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    await get().fetchSkill(id)
  },

  deleteSkill: async (id) => {
    await fetch(`${API}/${id}`, { method: 'DELETE' })
    set({ selectedSkill: null })
    await get().fetchSkills()
    await get().fetchStats()
  },

  bindSkill: async (agentId, skillId, confidence = 0.5) => {
    await fetch(`${API}/bind`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId, skill_id: skillId, confidence_score: confidence }),
    })
    await get().fetchSkill(skillId)
  },

  unbindSkill: async (agentId, skillId) => {
    await fetch(`${API}/unbind/${agentId}/${skillId}`, { method: 'DELETE' })
    await get().fetchSkill(skillId)
  },

  searchRegistries: async (query = '', registry = '', category = '') => {
    set({ registryLoading: true })
    try {
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      if (registry) params.set('registry', registry)
      if (category) params.set('category', category)
      const res = await fetch(`${API}/registry/search?${params}`)
      const data = await res.json()
      set({ registryResults: data.results || [], registryLoading: false })
    } catch {
      set({ registryLoading: false })
    }
  },

  fetchRegistryStats: async () => {
    try {
      const res = await fetch(`${API}/registry/stats`)
      const data = await res.json()
      set({ registryStats: data.registries || {} })
    } catch { /* ignore */ }
  },

  installFromRegistry: async (name, registry, category = 'general') => {
    try {
      const res = await fetch(`${API}/registry/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, registry, category }),
      })
      const result = await res.json()
      await get().fetchSkills()
      await get().fetchStats()
      return result
    } catch {
      return null
    }
  },
}))
