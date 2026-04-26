import { create } from 'zustand'
import { api } from '@/lib/api'
import type { Task, TaskStatus } from '@/types'

interface TaskStore {
  tasks: Task[]
  loading: boolean
  error: string | null
  fetchTasks: () => Promise<void>
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  removeTask: (id: string) => void
  moveTask: (id: string, status: TaskStatus) => Promise<void>
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  loading: false,
  error: null,

  fetchTasks: async () => {
    set({ loading: true, error: null })
    try {
      const tasks = await api.get<Task[]>('/tasks')
      set({ tasks, loading: false })
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  addTask: (task) => set((s) => ({ tasks: [task, ...s.tasks] })),

  updateTask: (id, updates) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),

  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),

  moveTask: async (id, status) => {
    // Optimistic update
    get().updateTask(id, { status })
    try {
      const updated = await api.patch<Task>(`/tasks/${id}`, { status })
      get().updateTask(id, updated)
    } catch {
      // Revert on error — refetch
      get().fetchTasks()
    }
  },
}))
