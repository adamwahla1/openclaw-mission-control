import { create } from 'zustand'
import { api } from '@/lib/api'
import type { Project } from '@/types'

interface ProjectStore {
  projects: Project[]
  loading: boolean
  error: string | null
  fetchProjects: () => Promise<void>
  addProject: (p: Project) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  removeProject: (id: string) => void
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null })
    try {
      const projects = await api.get<Project[]>('/projects')
      set({ projects, loading: false })
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  addProject: (p) => set((s) => ({ projects: [p, ...s.projects] })),

  updateProject: (id, updates) =>
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? { ...p, ...updates } : p)),
    })),

  removeProject: (id) => set((s) => ({ projects: s.projects.filter((p) => p.id !== id) })),
}))
