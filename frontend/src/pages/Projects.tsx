import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderKanban, Plus, Layers, FileText, Clock, Package } from 'lucide-react'
import { useProjectStore } from '@/store/projectStore'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { cn, formatRelative } from '@/lib/utils'
import type { Project } from '@/types'

const STATUS_VARIANT: Record<string, 'success' | 'info' | 'secondary'> = {
  active: 'success',
  completed: 'info',
  archived: 'secondary',
}

export default function Projects() {
  const navigate = useNavigate()
  const { projects, loading, fetchProjects, addProject } = useProjectStore()
  const [createOpen, setCreateOpen] = useState(false)
  const [bundling, setBundling] = useState(false)

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const handleAutoBundle = async () => {
    setBundling(true)
    try {
      await api.post('/projects/auto-bundle')
      await fetchProjects()
    } catch {
      // silently fail — store will show stale data
    } finally {
      setBundling(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleAutoBundle} disabled={bundling}>
            <Package size={14} className={cn('mr-1.5', bundling && 'animate-pulse')} />
            {bundling ? 'Bundling…' : 'Auto-Bundle'}
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus size={14} className="mr-1.5" />
            New Project
          </Button>
        </div>
      </div>

      {/* Content */}
      {loading && projects.length === 0 ? (
        <div className="flex items-center justify-center h-[50vh]">
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            Loading projects…
          </div>
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-[50vh] text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center mb-4">
            <FolderKanban size={32} className="text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold mb-1">No projects yet</h2>
          <p className="text-muted-foreground text-sm max-w-sm mb-4">
            Create a new project or use Auto-Bundle to automatically group tasks into projects.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleAutoBundle} disabled={bundling}>
              <Package size={14} className="mr-1.5" />
              Auto-Bundle
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus size={14} className="mr-1.5" />
              New Project
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onClick={() => navigate(`/projects/${project.id}`)}
            />
          ))}
        </div>
      )}

      {/* Create project dialog */}
      <CreateProjectDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(p) => { addProject(p); navigate(`/projects/${p.id}`) }}
      />
    </div>
  )
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  return (
    <Card
      className="cursor-pointer hover:border-primary/40 hover:shadow-md transition-all duration-150"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-snug">{project.name}</CardTitle>
          <Badge variant={STATUS_VARIANT[project.status] ?? 'secondary'}>
            {project.status}
          </Badge>
        </div>
        {project.description && (
          <CardDescription className="line-clamp-2">{project.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Layers size={12} />
            <span>{project.task_count ?? project.tasks?.length ?? 0} tasks</span>
          </div>
          {(project.files?.length ?? 0) > 0 && (
            <div className="flex items-center gap-1">
              <FileText size={12} />
              <span>{project.files!.length} files</span>
            </div>
          )}
          {project.auto_bundled === 1 && (
            <Badge variant="purple" className="text-[10px] px-1.5 py-0">auto-bundled</Badge>
          )}
          <div className="flex items-center gap-1 ml-auto">
            <Clock size={12} />
            <span>{formatRelative(project.created_at)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function CreateProjectDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (p: Project) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => { setName(''); setDescription(''); setError(null) }
  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const project = await api.post<Project>('/projects', {
        name: name.trim(),
        description: description.trim() || null,
      })
      onCreated(project)
      reset()
      onClose()
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
          </DialogHeader>
          <div className="px-6 space-y-4">
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Name</label>
              <Input
                autoFocus
                placeholder="Project name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Description</label>
              <Textarea
                placeholder="What is this project about?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? 'Creating…' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
