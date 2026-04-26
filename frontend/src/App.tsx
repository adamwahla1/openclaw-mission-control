import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useState } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import Dashboard from '@/pages/Dashboard'
import TaskBoard from '@/pages/TaskBoard'
import Projects from '@/pages/Projects'
import ProjectDetail from '@/pages/ProjectDetail'
import DebateRoom from '@/pages/DebateRoom'
import MemoryMap from '@/pages/MemoryMap'
import VirtualOffice from '@/pages/VirtualOffice'
import Autopilot from '@/pages/Autopilot'
import SkillsHub from '@/pages/SkillsHub'
import SecurityAudit from '@/pages/SecurityAudit'
import CostDashboard from '@/pages/CostDashboard'
import Settings from '@/pages/Settings'

export default function App() {
  const [gatewayConnected] = useState(false)

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden dark">
        <Sidebar gatewayConnected={gatewayConnected} />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tasks" element={<TaskBoard />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:id" element={<ProjectDetail />} />
              <Route path="/debate" element={<DebateRoom />} />
              <Route path="/memory" element={<MemoryMap />} />
              <Route path="/office" element={<VirtualOffice />} />
              <Route path="/autopilot" element={<Autopilot />} />
              <Route path="/skills" element={<SkillsHub />} />
              <Route path="/security" element={<SecurityAudit />} />
              <Route path="/costs" element={<CostDashboard />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
