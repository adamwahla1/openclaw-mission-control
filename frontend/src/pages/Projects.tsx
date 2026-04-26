import { FolderKanban } from 'lucide-react'

export default function Projects() {
  return (
    <div className="p-6">
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <div className="w-16 h-16 rounded-2xl bg-accent flex items-center justify-center mb-4">
          <FolderKanban size={32} className="text-muted-foreground" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Projects</h2>
        <p className="text-muted-foreground text-sm max-w-md">
          Auto-bundled project groups with handover docs
        </p>
      </div>
    </div>
  )
}
