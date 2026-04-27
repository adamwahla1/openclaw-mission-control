import { useEffect, useState } from 'react'
import {
  Puzzle, Plus, Trash2, Link2, Unlink, Search, Star,
  ExternalLink, Zap, Shield, Tag, Loader2, X, Download,
  Globe, Database, Package, TrendingUp, CheckCircle
} from 'lucide-react'
import { useSkillsStore } from '../store/skillsStore'
import type { Skill } from '../types'

const TYPE_COLORS: Record<string, string> = {
  internal: 'bg-blue-500/20 text-blue-300',
  external: 'bg-purple-500/20 text-purple-300',
  community: 'bg-emerald-500/20 text-emerald-300',
}

const CATEGORY_ICONS: Record<string, string> = {
  general: '🔧', coding: '💻', research: '🔍', writing: '✍️',
  analysis: '📊', creative: '🎨', communication: '💬', security: '🛡️',
  data: '📁', cloud: '☁️', business: '💼', legal: '⚖️', document: '📄', design: '🎨',
}

const REGISTRY_ICONS: Record<string, React.ReactNode> = {
  'skills.sh': <Globe size={14} className="text-emerald-400" />,
  'skills-directory': <Database size={14} className="text-blue-400" />,
  'anthropic': <Shield size={14} className="text-orange-400" />,
  'huggingface': <Package size={14} className="text-yellow-400" />,
}

const REGISTRY_COLORS: Record<string, string> = {
  'skills.sh': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'skills-directory': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'anthropic': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'huggingface': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
}

interface RegistrySkill {
  name: string
  description: string
  category: string
  skill_type: string
  source_url: string
  version: string
  author: string
  tags: string[]
  registry: string
  install_command: string
  popularity: number
}

interface RegistryStat {
  name: string
  skill_count: number
  categories: string[]
  top_skill: string
  top_popularity: number
}

export default function SkillsHub() {
  const { skills, stats, categories, selectedSkill, loading, fetchSkills, fetchStats, fetchCategories, fetchSkill, createSkill, deleteSkill, bindSkill, unbindSkill } = useSkillsStore()
  const [showCreate, setShowCreate] = useState(false)
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [catFilter, setCatFilter] = useState<string>('')
  const [form, setForm] = useState({ name: '', description: '', category: 'general', skill_type: 'internal', prompt_template: '', tags: '' })
  const [showBind, setShowBind] = useState(false)
  const [bindForm, setBindForm] = useState({ agent_id: '', confidence: 0.5 })

  // Registry browser state
  const [tab, setTab] = useState<'installed' | 'browse'>('installed')
  const [registrySearch, setRegistrySearch] = useState('')
  const [registryFilter, setRegistryFilter] = useState<string>('')
  const [registryCatFilter, setRegistryCatFilter] = useState<string>('')
  const [registryResults, setRegistryResults] = useState<RegistrySkill[]>([])
  const [registryStats, setRegistryStats] = useState<Record<string, RegistryStat>>({})
  const [registryLoading, setRegistryLoading] = useState(false)
  const [installing, setInstalling] = useState<string | null>(null)
  const [installed, setInstalled] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchSkills()
    fetchStats()
    fetchCategories()
    loadInstalledNames()
  }, [])

  useEffect(() => {
    fetchSkills(catFilter || undefined, typeFilter || undefined)
  }, [typeFilter, catFilter])

  const loadInstalledNames = async () => {
    const res = await fetch('/api/skills')
    const data = await res.json()
    setInstalled(new Set(data.map((s: any) => s.name)))
  }

  const searchRegistry = async () => {
    setRegistryLoading(true)
    try {
      const params = new URLSearchParams()
      if (registrySearch) params.set('q', registrySearch)
      if (registryFilter) params.set('registry', registryFilter)
      if (registryCatFilter) params.set('category', registryCatFilter)
      const res = await fetch(`/api/skills/registry/search?${params}`)
      const data = await res.json()
      setRegistryResults(data.results || [])
    } catch { /* ignore */ }
    setRegistryLoading(false)
  }

  const loadRegistryStats = async () => {
    try {
      const res = await fetch('/api/skills/registry/stats')
      const data = await res.json()
      setRegistryStats(data.registries || {})
    } catch { /* ignore */ }
  }

  const loadAllRegistrySkills = async () => {
    setRegistryLoading(true)
    try {
      const res = await fetch('/api/skills/registry/list')
      const data = await res.json()
      setRegistryResults(data.results || [])
    } catch { /* ignore */ }
    setRegistryLoading(false)
  }

  const installSkill = async (skill: RegistrySkill) => {
    setInstalling(skill.name)
    try {
      const res = await fetch('/api/skills/registry/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: skill.name, registry: skill.registry, category: skill.category }),
      })
      const data = await res.json()
      if (data.status === 'installed' || data.status === 'already_installed') {
        setInstalled(prev => new Set([...prev, skill.name]))
        await fetchSkills()
        await fetchStats()
      }
    } catch { /* ignore */ }
    setInstalling(null)
  }

  // Load registry data when switching to browse tab
  useEffect(() => {
    if (tab === 'browse') {
      loadRegistryStats()
      loadAllRegistrySkills()
    }
  }, [tab])

  const filtered = skills.filter(s =>
    !filter || s.name.toLowerCase().includes(filter.toLowerCase()) || s.description.toLowerCase().includes(filter.toLowerCase())
  )

  const handleCreate = async () => {
    if (!form.name.trim()) return
    await createSkill({
      ...form,
      tags: form.tags ? form.tags.split(',').map(t => t.trim()) : [],
    })
    setShowCreate(false)
    setForm({ name: '', description: '', category: 'general', skill_type: 'internal', prompt_template: '', tags: '' })
    await loadInstalledNames()
  }

  const handleBind = async () => {
    if (!selectedSkill || !bindForm.agent_id.trim()) return
    await bindSkill(bindForm.agent_id, selectedSkill.id, bindForm.confidence)
    setShowBind(false)
    setBindForm({ agent_id: '', confidence: 0.5 })
  }

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Header with tabs */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Puzzle size={20} className="text-purple-400" />
            <h2 className="text-lg font-semibold">Skills Hub</h2>
            {stats && <span className="text-xs text-muted-foreground">({stats.total_skills} installed)</span>}
          </div>
          <div className="flex items-center bg-white/5 rounded-lg p-0.5">
            <button
              onClick={() => setTab('installed')}
              className={`px-3 py-1.5 rounded-md text-sm transition ${
                tab === 'installed' ? 'bg-purple-500/20 text-purple-300' : 'text-muted-foreground hover:text-white'
              }`}
            >
              Installed
            </button>
            <button
              onClick={() => setTab('browse')}
              className={`px-3 py-1.5 rounded-md text-sm transition flex items-center gap-1 ${
                tab === 'browse' ? 'bg-emerald-500/20 text-emerald-300' : 'text-muted-foreground hover:text-white'
              }`}
            >
              <Globe size={14} /> Browse Registries
            </button>
          </div>
        </div>
        {tab === 'installed' && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-purple-500/20 text-purple-300 rounded-lg text-sm hover:bg-purple-500/30 transition"
          >
            <Plus size={14} /> Add Skill
          </button>
        )}
      </div>

      {tab === 'installed' ? (
        <InstalledView
          skills={filtered}
          stats={stats}
          categories={categories}
          selectedSkill={selectedSkill}
          loading={loading}
          filter={filter}
          typeFilter={typeFilter}
          catFilter={catFilter}
          setFilter={setFilter}
          setTypeFilter={setTypeFilter}
          setCatFilter={setCatFilter}
          fetchSkill={fetchSkill}
          deleteSkill={deleteSkill}
          bindSkill={bindSkill}
          unbindSkill={unbindSkill}
          showBind={showBind}
          setShowBind={setShowBind}
          bindForm={bindForm}
          setBindForm={setBindForm}
          handleBind={handleBind}
        />
      ) : (
        <BrowseView
          results={registryResults}
          registryStats={registryStats}
          loading={registryLoading}
          search={registrySearch}
          setSearch={setRegistrySearch}
          registryFilter={registryFilter}
          setRegistryFilter={setRegistryFilter}
          catFilter={registryCatFilter}
          setCatFilter={setRegistryCatFilter}
          onSearch={searchRegistry}
          onInstall={installSkill}
          installing={installing}
          installed={installed}
        />
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-[#1a1b1e] rounded-2xl p-6 w-[520px] border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Add New Skill</h3>
              <button onClick={() => setShowCreate(false)} className="text-white/40 hover:text-white"><X size={18} /></button>
            </div>
            <div className="flex flex-col gap-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Skill name" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500/50" />
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500/50" />
              <div className="flex gap-2">
                <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  {Object.keys(CATEGORY_ICONS).map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <select value={form.skill_type} onChange={e => setForm(f => ({ ...f, skill_type: e.target.value }))} className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  <option value="internal">Internal</option>
                  <option value="external">External</option>
                  <option value="community">Community</option>
                </select>
              </div>
              <textarea value={form.prompt_template} onChange={e => setForm(f => ({ ...f, prompt_template: e.target.value }))} placeholder="Prompt template (optional)" rows={3} className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500/50 resize-none font-mono" />
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="Tags (comma-separated)" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500/50" />
              <div className="flex justify-end gap-2 mt-2">
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-muted-foreground hover:text-white transition">Cancel</button>
                <button onClick={handleCreate} disabled={!form.name.trim()} className="px-4 py-2 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-400 disabled:opacity-30 transition">Create Skill</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Installed Skills View ──────────────────────────────────────────────

function InstalledView({ skills, stats, categories, selectedSkill, loading, filter, typeFilter, catFilter, setFilter, setTypeFilter, setCatFilter, fetchSkill, deleteSkill, bindSkill: _bindSkill, unbindSkill, showBind, setShowBind, bindForm, setBindForm, handleBind }: any) {
  return (
    <div className="flex-1 flex min-h-0">
      {/* Left: Skills list */}
      <div className="w-96 flex-shrink-0 flex flex-col gap-4 overflow-auto pr-4 border-r border-white/10">
        {/* Filters */}
        <div className="flex flex-col gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Search installed skills..." className="w-full bg-white/5 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-sm focus:outline-none focus:border-purple-500/50" />
          </div>
          <div className="flex gap-2">
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs focus:outline-none">
              <option value="">All types</option>
              <option value="internal">Internal</option>
              <option value="external">External</option>
              <option value="community">Community</option>
            </select>
            <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs focus:outline-none flex-1">
              <option value="">All categories</option>
              {categories.map((c: any) => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
            </select>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold">{stats.total_skills}</div>
              <div className="text-xs text-muted-foreground">Skills</div>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold">{stats.total_bindings}</div>
              <div className="text-xs text-muted-foreground">Bindings</div>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.02] border border-white/5 text-center">
              <div className="text-lg font-semibold">{Object.keys(stats.by_type).length}</div>
              <div className="text-xs text-muted-foreground">Types</div>
            </div>
          </div>
        )}

        {/* Skills list */}
        {loading && skills.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground"><Loader2 className="animate-spin mr-2" size={16} /> Loading...</div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {skills.map((skill: Skill) => (
              <button key={skill.id} onClick={() => fetchSkill(skill.id)}
                className={`text-left p-3 rounded-xl border transition hover:border-white/20 ${
                  selectedSkill?.id === skill.id ? 'border-purple-500/50 bg-purple-500/5' : 'border-white/5 bg-white/[0.02]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm flex items-center gap-1.5">{CATEGORY_ICONS[skill.category] || '🔧'} {skill.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[skill.skill_type] || 'bg-gray-500/20 text-gray-300'}`}>{skill.skill_type}</span>
                </div>
                <p className="text-xs text-muted-foreground truncate">{skill.description}</p>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-white/40">
                  <span className="flex items-center gap-1"><Zap size={10} /> {skill.use_count}</span>
                  <span className="flex items-center gap-1"><Star size={10} /> {skill.trust_score?.toFixed(0)}</span>
                </div>
              </button>
            ))}
            {skills.length === 0 && <div className="text-center py-8 text-muted-foreground text-sm">No skills found</div>}
          </div>
        )}
      </div>

      {/* Right: Skill detail */}
      <div className="flex-1 pl-6 overflow-auto">
        {selectedSkill ? (
          <SkillDetail skill={selectedSkill} onBind={() => setShowBind(true)} onUnbind={unbindSkill} onDelete={() => deleteSkill(selectedSkill.id)} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4"><Puzzle size={32} className="text-purple-400/50" /></div>
            <p className="text-muted-foreground text-sm">Select a skill to view details</p>
          </div>
        )}
      </div>

      {/* Bind modal */}
      {showBind && selectedSkill && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowBind(false)}>
          <div className="bg-[#1a1b1e] rounded-2xl p-6 w-[400px] border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Bind Skill to Agent</h3>
              <button onClick={() => setShowBind(false)} className="text-white/40 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-3">Bind <span className="text-white font-medium">{selectedSkill.name}</span> to an agent</p>
            <div className="flex flex-col gap-3">
              <input value={bindForm.agent_id} onChange={e => setBindForm((f: any) => ({ ...f, agent_id: e.target.value }))} placeholder="Agent ID" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none" />
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Confidence:</label>
                <input type="range" min="0" max="1" step="0.1" value={bindForm.confidence} onChange={e => setBindForm((f: any) => ({ ...f, confidence: parseFloat(e.target.value) }))} className="flex-1" />
                <span className="text-sm w-8">{bindForm.confidence.toFixed(1)}</span>
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowBind(false)} className="px-4 py-2 text-sm text-muted-foreground hover:text-white transition">Cancel</button>
                <button onClick={handleBind} disabled={!bindForm.agent_id.trim()} className="px-4 py-2 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-400 disabled:opacity-30 transition">Bind</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Browse Registries View ─────────────────────────────────────────────

function BrowseView({ results, registryStats, loading, search, setSearch, registryFilter, setRegistryFilter, catFilter, setCatFilter, onSearch, onInstall, installing, installed }: {
  results: RegistrySkill[]
  registryStats: Record<string, RegistryStat>
  loading: boolean
  search: string
  setSearch: (s: string) => void
  registryFilter: string
  setRegistryFilter: (s: string) => void
  catFilter: string
  setCatFilter: (s: string) => void
  onSearch: () => void
  onInstall: (skill: RegistrySkill) => void
  installing: string | null
  installed: Set<string>
}) {
  // Get unique categories from results
  const allCategories = Array.from(new Set(results.map(r => r.category))).sort()

  return (
    <div className="flex-1 flex min-h-0">
      {/* Left: Registry list */}
      <div className="w-96 flex-shrink-0 flex flex-col gap-4 overflow-auto pr-4 border-r border-white/10">
        {/* Registry stats cards */}
        <div className="grid grid-cols-2 gap-2">
          {Object.values(registryStats).map(stat => (
            <div key={stat.name} className={`p-3 rounded-xl border ${REGISTRY_COLORS[stat.name] || 'border-white/5'}`}>
              <div className="flex items-center gap-2 mb-1">
                {REGISTRY_ICONS[stat.name]}
                <span className="text-sm font-medium">{stat.name}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {stat.skill_count} skills · top: {stat.top_skill}
              </div>
            </div>
          ))}
        </div>

        {/* Search */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && onSearch()}
              placeholder="Search all registries..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-sm focus:outline-none focus:border-emerald-500/50"
            />
          </div>
          <button onClick={onSearch} className="px-3 py-1.5 bg-emerald-500/20 text-emerald-300 rounded-lg text-sm hover:bg-emerald-500/30 transition">Search</button>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <select value={registryFilter} onChange={e => { setRegistryFilter(e.target.value); setTimeout(onSearch, 100) }} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs focus:outline-none flex-1">
            <option value="">All registries</option>
            <option value="skills.sh">skills.sh</option>
            <option value="skills-directory">Skills Directory</option>
            <option value="anthropic">Anthropic</option>
            <option value="huggingface">Hugging Face</option>
          </select>
          <select value={catFilter} onChange={e => { setCatFilter(e.target.value); setTimeout(onSearch, 100) }} className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs focus:outline-none flex-1">
            <option value="">All categories</option>
            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="text-xs text-muted-foreground">{results.length} skills available</div>

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground"><Loader2 className="animate-spin mr-2" size={16} /> Loading registries...</div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {results.map(skill => {
              const isInstalled = installed.has(skill.name)
              const isInstalling = installing === skill.name
              return (
                <div key={`${skill.registry}-${skill.name}`} className="p-3 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 transition">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-sm font-medium">{CATEGORY_ICONS[skill.category] || '🔧'} {skill.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${REGISTRY_COLORS[skill.registry] || 'border-white/10'}`}>
                          {skill.registry}
                        </span>
                        {skill.version && <span className="text-[10px] text-white/30">v{skill.version}</span>}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{skill.description}</p>
                      <div className="flex items-center gap-3 mt-1.5 text-xs text-white/40">
                        <span className="flex items-center gap-1"><TrendingUp size={10} /> {skill.popularity.toLocaleString()}</span>
                        <span>by {skill.author}</span>
                      </div>
                      {skill.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {skill.tags.slice(0, 3).map(tag => (
                            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-white/5 rounded text-white/40">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => !isInstalled && !isInstalling && onInstall(skill)}
                      disabled={isInstalled || isInstalling}
                      className={`flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition ${
                        isInstalled ? 'bg-emerald-500/20 text-emerald-300 cursor-default' :
                        isInstalling ? 'bg-amber-500/20 text-amber-300 cursor-wait' :
                        'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 cursor-pointer'
                      }`}
                    >
                      {isInstalled ? <><CheckCircle size={12} /> Installed</> :
                       isInstalling ? <><Loader2 size={12} className="animate-spin" /> Installing</> :
                       <><Download size={12} /> Install</>}
                    </button>
                  </div>
                </div>
              )
            })}
            {results.length === 0 && (
              <div className="text-center py-8 text-muted-foreground text-sm">No skills found. Try a different search.</div>
            )}
          </div>
        )}
      </div>

      {/* Right: Detail panel for selected registry skill */}
      <div className="flex-1 pl-6 overflow-auto">
        <RegistryDetailPanel />
      </div>
    </div>
  )
}

function RegistryDetailPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4"><Globe size={32} className="text-emerald-400/50" /></div>
      <h3 className="text-lg font-semibold mb-1">Browse External Registries</h3>
      <p className="text-muted-foreground text-sm max-w-sm">
        Search and install skills from <strong>skills.sh</strong>, <strong>Skills Directory</strong>, <strong>Anthropic</strong>, and <strong>Hugging Face</strong> directly into your Mission Control.
      </p>
      <div className="grid grid-cols-2 gap-3 mt-6 w-full max-w-md">
        {[
          { name: 'skills.sh', desc: 'Vercel\'s npm-like registry for agent skills', color: 'emerald' },
          { name: 'Skills Directory', desc: 'Security-scanned Claude skills (36k+ indexed)', color: 'blue' },
          { name: 'Anthropic', desc: 'Official Claude skills — PDF, DOCX, PPTX, API', color: 'orange' },
          { name: 'Hugging Face', desc: 'ML/AI skills — datasets, models, training', color: 'yellow' },
        ].map(r => (
          <div key={r.name} className={`p-3 rounded-xl bg-${r.color}-500/5 border border-${r.color}-500/20 text-left`}>
            <div className="text-sm font-medium">{r.name}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{r.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Skill Detail ───────────────────────────────────────────────────────

function SkillDetail({ skill, onBind, onUnbind, onDelete }: {
  skill: Skill
  onBind: () => void
  onUnbind: (agentId: string, skillId: string) => void
  onDelete: () => void
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{CATEGORY_ICONS[skill.category] || '🔧'}</span>
            <h2 className="text-xl font-semibold">{skill.name}</h2>
            <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[skill.skill_type]}`}>{skill.skill_type}</span>
            {skill.version && <span className="text-xs text-muted-foreground">v{skill.version}</span>}
          </div>
          <p className="text-muted-foreground text-sm mt-1">{skill.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onBind} className="flex items-center gap-1 px-3 py-1.5 bg-purple-500/20 text-purple-300 rounded-lg text-sm hover:bg-purple-500/30 transition">
            <Link2 size={14} /> Bind to Agent
          </button>
          <button onClick={onDelete} className="p-1.5 text-red-400/50 hover:text-red-400 transition"><Trash2 size={16} /></button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-sm text-muted-foreground">Usage</div>
          <div className="text-xl font-semibold">{skill.use_count}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-sm text-muted-foreground">Success Rate</div>
          <div className="text-xl font-semibold">{skill.use_count > 0 ? ((skill.success_count / skill.use_count) * 100).toFixed(0) + '%' : '—'}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-sm text-muted-foreground">Trust Score</div>
          <div className="text-xl font-semibold">{skill.trust_score?.toFixed(0)}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="text-sm text-muted-foreground">Avg Latency</div>
          <div className="text-xl font-semibold">{skill.avg_latency_ms?.toFixed(0) || '—'}ms</div>
        </div>
      </div>

      {skill.tags && skill.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {skill.tags.map(tag => (
            <span key={tag} className="flex items-center gap-1 px-2 py-0.5 bg-white/5 rounded-full text-xs text-muted-foreground"><Tag size={10} /> {tag}</span>
          ))}
        </div>
      )}

      {skill.prompt_template && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Prompt Template</h3>
          <pre className="p-3 rounded-xl bg-black/30 border border-white/5 text-xs font-mono whitespace-pre-wrap text-white/70 max-h-48 overflow-auto">{skill.prompt_template}</pre>
        </div>
      )}

      {skill.source_url && (
        <div className="flex items-center gap-2 text-sm">
          <ExternalLink size={14} className="text-purple-400" />
          <a href={skill.source_url} target="_blank" rel="noopener noreferrer" className="text-purple-300 hover:underline truncate">{skill.source_url}</a>
        </div>
      )}

      {skill.bindings && skill.bindings.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Bound Agents ({skill.bindings.length})</h3>
          <div className="flex flex-col gap-1.5">
            {skill.bindings.map((binding: any) => (
              <div key={binding.id} className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
                <div className="flex items-center gap-2">
                  <Shield size={14} className="text-blue-400" />
                  <span className="text-sm">{binding.agent_name || binding.agent_id}</span>
                  <span className="text-xs text-muted-foreground">confidence: {binding.confidence_score.toFixed(2)}</span>
                </div>
                <button onClick={() => onUnbind(binding.agent_id, skill.id)} className="flex items-center gap-1 text-xs text-red-400/60 hover:text-red-400 transition">
                  <Unlink size={12} /> Unbind
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
