import { useLocation } from 'react-router-dom'
import { Bell, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/tasks': 'Task Board',
  '/projects': 'Projects',
  '/debate': 'Debate Room',
  '/memory': 'Memory Map',
  '/office': 'Virtual Office',
  '/autopilot': 'Autopilot',
  '/skills': 'Skills Hub',
  '/security': 'Security Audit',
  '/costs': 'Cost Dashboard',
  '/settings': 'Settings',
}

export function Header() {
  const location = useLocation()
  const title = pageTitles[location.pathname] || 'Mission Control'

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b bg-card/50 backdrop-blur-sm">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="text-muted-foreground">
          <Search size={18} />
        </Button>
        <Button variant="ghost" size="icon" className="text-muted-foreground relative">
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full" />
        </Button>
      </div>
    </header>
  )
}
