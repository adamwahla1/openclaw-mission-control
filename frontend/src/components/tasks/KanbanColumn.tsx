import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { Plus } from 'lucide-react'
import type { Task, TaskStatus } from '@/types'
import TaskCard from './TaskCard'
import { cn } from '@/lib/utils'

interface Props {
  id: TaskStatus
  title: string
  tasks: Task[]
  color: string
  onTaskClick: (task: Task) => void
  onAddTask: (status: TaskStatus) => void
}

export default function KanbanColumn({ id, title, tasks, color, onTaskClick, onAddTask }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'flex flex-col w-72 shrink-0 rounded-2xl bg-secondary/40 border border-border transition-colors duration-150',
        isOver && 'border-primary/50 bg-primary/5'
      )}
    >
      {/* Column header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={cn('w-2 h-2 rounded-full', color)} />
          <span className="text-sm font-medium">{title}</span>
          <span className="text-xs text-muted-foreground bg-secondary rounded-full px-1.5 py-0.5">
            {tasks.length}
          </span>
        </div>
        <button
          onClick={() => onAddTask(id)}
          className="p-0.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Task list */}
      <SortableContext items={tasks.map(t => t.id)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 min-h-32 px-3 pb-3 space-y-2 overflow-y-auto max-h-[calc(100vh-200px)]">
          {tasks.map(task => (
            <TaskCard key={task.id} task={task} onClick={onTaskClick} />
          ))}
          {tasks.length === 0 && (
            <div className="flex items-center justify-center h-16 text-xs text-muted-foreground/50">
              Drop tasks here
            </div>
          )}
        </div>
      </SortableContext>
    </div>
  )
}
