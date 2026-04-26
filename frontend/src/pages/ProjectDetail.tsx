import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Pencil, Layers, FileText, FileCode, File, FileImage,
  Upload, Bot, BookOpen, Plus, Clock, ChevronRight,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn, formatRelative, formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import type { Project, ProjectFile, Handover, Task } from '@/types'

const STATUS_VARIANT: Record<string, 'success' | 'info' | 'secondary'> = {
  active: 'success', completed: 'info', archived: 'secondary',
}

const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-yellow-500', low: 'bg-green-500',
}

const FILE_ICONS: Record<string, typeof FileText> = {
  py: FileCode, js: FileCode, ts: FileCode, tsx: FileCode, jsx: FileCode,
  md: BookOpen, txt: File, json: FileCode, yaml: FileCode, yml: FileCode,
  png: FileImage, jpg: FileImage, svg: FileImage,
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [fileContent, setFileContent] = useState<ProjectFile | null>(null)
  const [handoverContent, setHandoverContent] = useState<Handover | null>(null)
  const [addTaskOpen, setAddTaskOpen] = useState(false)
  const [unassignedTasks, setUnassignedTasks] = useState<Task[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)
  const [generateHandover, setGenerateHandover] = useState(false)

  const fetchProject = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const p = await api.get<Project>(`/projects/${id}`)
      setProject(p)
    } catch {
      // project not found
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchProject() }, [fetchProject])

  const handleAddTask = async (taskId: string) => {
    if (!id) return
    try {
      await api.post(`/projects/${id}/tasks`, { task_id: taskId })
      await fetchProject()
      setAddTaskOpen(false)
    } catch { /* ignore */ }
  }

  const handleFetchUnassigned = async () => {
    try {
      const tasks = await api.get<Task[]>('/tasks')
      setUnassignedTasks(tasks.filter((t) => !t.project_id))
      setAddTaskOpen(true)
    } catch { /* ignore */ }
  }

  const handleUpload = async (name: string, content: string) => {
    if (!id) return
    try {
      await api.post(`/projects/${id}/files`, { name, content })
      await fetchProject()
      setUploadOpen(false)
    } catch { /* ignore */ }
  }

  const handleGenerateHandover = async () => {
    if (!id) return
    setGenerateHandover(true)
    try {
      await api.post(`/projects/${id}/handovers`)
      await fetchProject()
    } catch { /* ignore */ }
    finally { setGenerateHandover(false) }
  }

  const handleEditProject = async (data: { name: string; description: string; status: string }) => {
    if (!id) return
    try {
      const updated = await api.patch<Project>(`/projects/${id}`, data)
      setProject(updated)
      setEditOpen(false)
    } catch { /* ignore */ }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          Loading project…
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] text-center">
        <h2 className="text-lg font-semibold mb-2">Project not found</h2>
        <Button variant="outline" size="sm" onClick={() => navigate('/projects')}>
          <ArrowLeft size={14} className="mr-1.5" />
          Back to Projects
        </Button>
      </div>
    )
  }

  const tasks = project.tasks ?? []
  const files = project.files ?? []
  const handovers = project.handovers ?? []

  return (
    <div className="p-6 space-y-6">
      {/* Top bar */}
      <div className="space-y-3">
        <button
          onClick={() => navigate('/projects')}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft size={14} />
          Projects
        </button>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
              <Badge variant={STATUS_VARIANT[project.status] ?? 'secondary'}>
                {project.status}
              </Badge>
            </div>
            {project.description && (
              <p className="text-muted-foreground text-sm">{project.description}</p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil size={14} className="mr-1.5" />
            Edit
          </Button>
        </div>
      </div>

      {/* Three-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Tasks column */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <Layers size={14} />
                Tasks
                <span className="text-muted-foreground font-normal">({tasks.length})</span>
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={handleFetchUnassigned}>
                <Plus size={14} />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {tasks.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">No tasks in this project</p>
            ) : (
              tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-2 p-2.5 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors cursor-pointer group"
                >
                  <span className={cn('w-2 h-2 rounded-full shrink-0', PRIORITY_DOT[task.priority])} />
                  <span className="text-sm flex-1 truncate">{task.title}</span>
                  <Badge variant="outline" className="text-[10px] shrink-0">{task.status.replace('_', ' ')}</Badge>
                  <ChevronRight size={12} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Files column */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <FileText size={14} />
                Files
                <span className="text-muted-foreground font-normal">({files.length})</span>
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload size={14} />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {files.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">No files yet</p>
            ) : (
              files.map((file) => {
                const ext = file.name.split('.').pop() ?? ''
                const Icon = FILE_ICONS[ext] ?? FileText
                return (
                  <div
                    key={file.id}
                    className="flex items-center gap-2.5 p-2.5 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors cursor-pointer"
                    onClick={() => setFileContent(file)}
                  >
                    <Icon size={14} className="text-muted-foreground shrink-0" />
                    <span className="text-sm flex-1 truncate">{file.name}</span>
                    {file.size_bytes != null && (
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {file.size_bytes < 1024 ? `${file.size_bytes} B` : `${Math.round(file.size_bytes / 1024)} KB`}
                      </span>
                    )}
                    <span className="text-[10px] text-muted-foreground shrink-0">
                      {formatRelative(file.created_at)}
                    </span>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        {/* Handovers column */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <BookOpen size={14} />
                Handovers
                <span className="text-muted-foreground font-normal">({handovers.length})</span>
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleGenerateHandover}
                disabled={generateHandover}
              >
                {generateHandover ? (
                  <div className="w-3.5 h-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Plus size={14} />
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {handovers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">No handover documents yet</p>
            ) : (
              handovers.map((h) => (
                <div
                  key={h.id}
                  className="flex items-center gap-2.5 p-2.5 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors cursor-pointer"
                  onClick={() => setHandoverContent(h)}
                >
                  <BookOpen size={14} className="text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{h.title}</p>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                      {h.agent_id && (
                        <span className="flex items-center gap-0.5">
                          <Bot size={10} />
                          Agent
                        </span>
                      )}
                      <span className="flex items-center gap-0.5">
                        <Clock size={10} />
                        {formatDate(h.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Edit project dialog */}
      <EditProjectDialog
        project={project}
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onSave={handleEditProject}
      />

      {/* Add task dialog */}
      <AddTaskDialog
        tasks={unassignedTasks}
        open={addTaskOpen}
        onClose={() => setAddTaskOpen(false)}
        onAdd={handleAddTask}
      />

      {/* Upload file dialog */}
      <UploadFileDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={handleUpload}
      />

      {/* File content modal */}
      <Dialog open={!!fileContent} onOpenChange={(o) => !o && setFileContent(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>{fileContent?.name}</DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-2">
            <pre className="text-xs bg-secondary rounded-lg p-4 overflow-auto max-h-[55vh] whitespace-pre-wrap font-mono">
              {fileContent?.content ?? '(no content)'}
            </pre>
          </div>
        </DialogContent>
      </Dialog>

      {/* Handover content modal */}
      <Dialog open={!!handoverContent} onOpenChange={(o) => !o && setHandoverContent(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>{handoverContent?.title}</DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-2">
            <div className="text-sm text-muted-foreground flex items-center gap-2 mb-3">
              {handoverContent?.agent_id && (
                <span className="flex items-center gap-1">
                  <Bot size={12} />
                  Agent
                </span>
              )}
              {handoverContent && (
                <span>{formatDate(handoverContent.created_at)}</span>
              )}
            </div>
            <div className="bg-secondary rounded-lg p-4 overflow-auto max-h-[55vh]">
              <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
                {handoverContent?.content_md}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function EditProjectDialog({
  project,
  open,
  onClose,
  onSave,
}: {
  project: Project
  open: boolean
  onClose: () => void
  onSave: (data: { name: string; description: string; status: string }) => void
}) {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description ?? '')
  const [status, setStatus] = useState(project.status)

  useEffect(() => {
    if (open) {
      setName(project.name)
      setDescription(project.description ?? '')
      setStatus(project.status)
    }
  }, [open, project])

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Project</DialogTitle>
        </DialogHeader>
        <div className="px-6 space-y-4">
          <div>
            <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Description</label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Status</label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onSave({ name, description, status })}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AddTaskDialog({
  tasks,
  open,
  onClose,
  onAdd,
}: {
  tasks: Task[]
  open: boolean
  onClose: () => void
  onAdd: (taskId: string) => void
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Task to Project</DialogTitle>
        </DialogHeader>
        <div className="px-6">
          {tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No unassigned tasks available
            </p>
          ) : (
            <div className="space-y-1.5 max-h-[40vh] overflow-y-auto">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-2 p-2.5 rounded-lg hover:bg-secondary cursor-pointer transition-colors"
                  onClick={() => onAdd(task.id)}
                >
                  <span className={cn('w-2 h-2 rounded-full shrink-0', PRIORITY_DOT[task.priority])} />
                  <span className="text-sm flex-1 truncate">{task.title}</span>
                  <Badge variant="outline" className="text-[10px] shrink-0">{task.status.replace('_', ' ')}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function UploadFileDialog({
  open,
  onClose,
  onUpload,
}: {
  open: boolean
  onClose: () => void
  onUpload: (name: string, content: string) => void
}) {
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => { setName(''); setContent('') }
  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    try {
      await onUpload(name.trim(), content)
      reset()
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Upload File</DialogTitle>
          </DialogHeader>
          <div className="px-6 space-y-4">
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">File Name</label>
              <Input
                autoFocus
                placeholder="e.g. notes.md"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-medium mb-1.5 block">Content</label>
              <Textarea
                placeholder="File content…"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={6}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? 'Uploading…' : 'Upload'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
