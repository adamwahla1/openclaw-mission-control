import { useEffect, useState, useCallback } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import { useTaskStore } from '@/store/taskStore'
import { useSSE } from '@/hooks/useSSE'
import type { Task, TaskStatus } from '@/types'
import KanbanColumn from '@/components/tasks/KanbanColumn'
import TaskCard from '@/components/tasks/TaskCard'
import TaskDrawer from '@/components/tasks/TaskDrawer'
import CreateTaskModal from '@/components/tasks/CreateTaskModal'
import { Button } from '@/components/ui/button'
import { Plus, RefreshCw, Filter } from 'lucide-react'

const COLUMNS: { id: TaskStatus; title: string; color: string }[] = [
  { id: 'inbox', title: 'Inbox', color: 'bg-slate-400' },
  { id: 'assigned', title: 'Assigned', color: 'bg-blue-500' },
  { id: 'in_progress', title: 'In Progress', color: 'bg-yellow-500' },
  { id: 'review', title: 'Review', color: 'bg-orange-500' },
  { id: 'quality_review', title: 'QA Review', color: 'bg-purple-500' },
  { id: 'done', title: 'Done', color: 'bg-green-500' },
  { id: 'archived', title: 'Archived', color: 'bg-slate-600' },
]

export default function TaskBoard() {
  useSSE()
  const { tasks, loading, fetchTasks, moveTask } = useTaskStore()
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createStatus, setCreateStatus] = useState<TaskStatus>('inbox')

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  useEffect(() => { fetchTasks() }, [fetchTasks])

  const getColumnTasks = useCallback(
    (status: TaskStatus) => tasks.filter(t => t.status === status),
    [tasks]
  )

  const handleDragStart = (e: DragStartEvent) => {
    const task = tasks.find(t => t.id === e.active.id)
    setActiveTask(task || null)
  }

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveTask(null)
    const { active, over } = e
    if (!over) return

    const targetStatus = COLUMNS.find(c => c.id === over.id)?.id
      ?? tasks.find(t => t.id === over.id)?.status

    if (!targetStatus) return
    const task = tasks.find(t => t.id === active.id)
    if (!task || task.status === targetStatus) return

    moveTask(task.id, targetStatus)
  }

  const handleAddTask = (status: TaskStatus) => {
    setCreateStatus(status)
    setCreateOpen(true)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={fetchTasks} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </Button>
          <Button variant="ghost" size="sm">
            <Filter size={14} className="mr-1.5" />
            Filter
          </Button>
        </div>
        <Button size="sm" onClick={() => { setCreateStatus('inbox'); setCreateOpen(true) }}>
          <Plus size={14} className="mr-1.5" />
          New Task
        </Button>
      </div>

      {/* Board */}
      <div className="flex-1 overflow-x-auto p-6">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 h-full">
            {COLUMNS.map(col => (
              <KanbanColumn
                key={col.id}
                id={col.id}
                title={col.title}
                color={col.color}
                tasks={getColumnTasks(col.id)}
                onTaskClick={setSelectedTask}
                onAddTask={handleAddTask}
              />
            ))}
          </div>

          <DragOverlay>
            {activeTask && (
              <div className="rotate-2 shadow-2xl">
                <TaskCard task={activeTask} onClick={() => {}} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Task detail drawer */}
      {selectedTask && (
        <TaskDrawer
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {/* Create task modal */}
      <CreateTaskModal
        open={createOpen}
        initialStatus={createStatus}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  )
}
