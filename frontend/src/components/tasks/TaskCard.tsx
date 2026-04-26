import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Bot, Clock } from 'lucide-react'
import type { Task } from '@/types'
import { cn } from '@/lib/utils'
import { formatRelative } from '@/lib/utils'

const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
}

interface Props {
  task: Task
  onClick: (task: Task) => void
}

export default function TaskCard({ task, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group relative bg-card border border-border rounded-xl p-3.5 cursor-pointer hover:border-primary/40 hover:shadow-md transition-all duration-150',
        isDragging && 'shadow-2xl ring-2 ring-primary/30'
      )}
      onClick={() => onClick(task)}
    >
      {/* Drag handle */}
      <div
        {...attributes}
        {...listeners}
        className="absolute left-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-40 cursor-grab active:cursor-grabbing"
        onClick={e => e.stopPropagation()}
      >
        <GripVertical size={14} />
      </div>

      <div className="pl-2">
        {/* Priority dot + title */}
        <div className="flex items-start gap-2 mb-2">
          <span className={cn('mt-1.5 w-2 h-2 rounded-full shrink-0', PRIORITY_DOT[task.priority])} />
          <p className="text-sm font-medium leading-snug line-clamp-2">{task.title}</p>
        </div>

        {/* Tags */}
        {task.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {task.tags.slice(0, 3).map(t => (
              <span key={t} className="px-1.5 py-0.5 rounded text-[10px] bg-secondary text-secondary-foreground">
                {t}
              </span>
            ))}
            {task.tags.length > 3 && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-secondary text-muted-foreground">
                +{task.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-1">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <Clock size={10} />
            <span>{formatRelative(task.created_at)}</span>
          </div>
          {task.assigned_agent_id && (
            <div className="flex items-center gap-1 text-[10px] text-blue-400">
              <Bot size={10} />
              <span>Agent</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
