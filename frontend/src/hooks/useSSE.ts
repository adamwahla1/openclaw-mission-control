import { useEffect } from 'react'
import { useTaskStore } from '@/store/taskStore'
import type { Task } from '@/types'

export function useSSE() {
  const { addTask, updateTask, removeTask } = useTaskStore()

  useEffect(() => {
    const es = new EventSource('/events')

    const on = (event: string, handler: (data: unknown) => void) => {
      es.addEventListener(event, (e: MessageEvent) => {
        try { handler(JSON.parse(e.data)) } catch { /* ignore parse errors */ }
      })
    }

    on('task.created', (d) => addTask(d as Task))
    on('task.updated', (d) => { const t = d as Task; updateTask(t.id, t) })
    on('task.deleted', (d) => removeTask((d as { id: string }).id))

    return () => es.close()
  }, [addTask, updateTask, removeTask])
}
