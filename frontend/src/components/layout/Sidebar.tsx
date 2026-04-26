import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  KanbanSquare,
  FolderKanban,
  MessageSquare,
  Brain,
  Building2,
  Rocket,
  Puzzle,
  Shield,
  DollarSign,
  Settings,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  section?: string
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <LayoutDashboard size={20} />, section: 'core' },
  { label: 'Tasks', path: '/tasks', icon: <KanbanSquare size={20} />, section: 'core' },
  { label: 'Projects', path: '/projects', icon: <FolderKanban size={20} />, section: 'core' },
  { label: 'Debate Room', path: '/debate', icon: <MessageSquare size={20} />, section: 'core' },
  { label: 'Memory Map', path: '/memory', icon: <Brain size={20} />, section: 'intelligence' },
  { label: 'Virtual Office', path: '/office', icon: <Building2 size={20} />, section: 'intelligence' },
  { label: 'Autopilot', path: '/autopilot', icon: <Rocket size={20} />, section: 'automation' },
  { label: 'Skills Hub', path: '/skills', icon: <Puzzle size={20} />, section: 'automation' },
  { label: 'Security', path: '/security', icon: <Shield size={20} />, section: 'ops' },
  { label: 'Costs', path: '/costs', icon: <DollarSign size={20} />, section: 'ops' },
  { label: 'Settings', path: '/settings', icon: <Settings size={20} />, section: 'system' },
]

const sectionLabels: Record<string, string> = {
  core: 'Mission Control',
  intelligence: 'Intelligence',
  automation: 'Automation',
  ops: 'Operations',
  system: 'System',
}

interface SidebarProps {
  gatewayConnected: boolean
}

export function Sidebar({ gatewayConnected }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  const grouped = navItems.reduce<Record<string, NavItem[]>>((acc, item) => {
    const section = item.section || 'other'
    if (!acc[section]) acc[section] = []
    acc[section].push(item)
    return acc
  }, {})

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'flex flex-col h-screen border-r bg-card transition-all duration-200',
          collapsed ? 'w-16' : 'w-56'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 border-b">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
            MC
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight truncate">
              Mission Control
            </span>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {Object.entries(grouped).map(([section, items]) => (
            <div key={section} className="mb-3">
              {!collapsed && (
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {sectionLabels[section] || section}
                </div>
              )}
              {items.map((item) => (
                <Tooltip key={item.path}>
                  <TooltipTrigger asChild>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm transition-colors',
                          isActive
                            ? 'bg-accent text-accent-foreground font-medium'
                            : 'text-muted-foreground hover:text-foreground hover:bg-accent/50',
                          collapsed && 'justify-center px-0'
                        )
                      }
                    >
                      {item.icon}
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  </TooltipTrigger>
                  {collapsed && (
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  )}
                </Tooltip>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t p-2 space-y-1">
          {/* Gateway status */}
          <div
            className={cn(
              'flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs',
              collapsed && 'justify-center px-0'
            )}
          >
            {gatewayConnected ? (
              <Wifi size={16} className="text-green-500 shrink-0" />
            ) : (
              <WifiOff size={16} className="text-red-500 shrink-0" />
            )}
            {!collapsed && (
              <span className={gatewayConnected ? 'text-green-500' : 'text-red-500'}>
                {gatewayConnected ? 'Gateway Connected' : 'Gateway Offline'}
              </span>
            )}
          </div>

          {/* Collapse toggle */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center justify-center w-full py-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </aside>
    </TooltipProvider>
  )
}
