import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, Database, MessageSquare, FileText, Trash2, Search, X,
  CheckCircle, Clock, Users, Globe, Sparkles, Lightbulb, Library
} from 'lucide-react'
import { knowledgeApi, searchApi, storyApi, type Knowledge, type SearchResponse, type Series } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type Tab = 'knowledge' | 'characters' | 'world_rules' | 'foreshadowing' | 'facts'

interface StoryElement {
  id: number
  name?: string
  title?: string
  description?: string
  verification_status?: string
  auto_extracted?: boolean
  created_at: string
  [key: string]: any
}

export function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<Tab>('knowledge')
  const [knowledge, setKnowledge] = useState<Knowledge[]>([])
  const [characters, setCharacters] = useState<StoryElement[]>([])
  const [worldRules, setWorldRules] = useState<StoryElement[]>([])
  const [foreshadowing, setForeshadowing] = useState<StoryElement[]>([])
  const [facts, setFacts] = useState<StoryElement[]>([])
  
  const [filter, setFilter] = useState<string | null>(null)
  const [verificationFilter, setVerificationFilter] = useState<string | null>('approved')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [formData, setFormData] = useState({ source_type: 'document', title: '', content: '', tags: '' })
  const [loading, setLoading] = useState(true)
  
  // Series selector
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    loadSeriesList()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadStoryElements()
      loadPendingCount()
    }
  }, [selectedSeriesId, activeTab, verificationFilter])

  useEffect(() => {
    if (activeTab === 'knowledge') {
      loadKnowledge()
    }
  }, [filter, activeTab])

  const loadSeriesList = async () => {
    try {
      const data = await storyApi.listSeries()
      setSeriesList(data)
      if (data.length > 0) {
        setSelectedSeriesId(data[0].id)
      }
    } catch (error) {
      console.error('Failed to load series:', error)
    }
  }

  const loadPendingCount = async () => {
    if (!selectedSeriesId) return
    try {
      const res = await fetch(`${API_BASE}/verification/stats/${selectedSeriesId}`)
      const data = await res.json()
      setPendingCount(data.total_pending || 0)
    } catch (error) {
      console.error('Failed to load pending count:', error)
    }
  }

  const loadStoryElements = async () => {
    if (!selectedSeriesId) return
    setLoading(true)
    
    try {
      if (activeTab === 'characters') {
        const res = await fetch(`${API_BASE}/story/characters/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setCharacters(data)
      } else if (activeTab === 'world_rules') {
        const res = await fetch(`${API_BASE}/story/world-rules/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setWorldRules(data)
      } else if (activeTab === 'foreshadowing') {
        const res = await fetch(`${API_BASE}/story/foreshadowing/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setForeshadowing(data)
      } else if (activeTab === 'facts') {
        const res = await fetch(`${API_BASE}/story/facts/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setFacts(data)
      }
    } catch (error) {
      console.error('Failed to load story elements:', error)
    }
    setLoading(false)
  }

  const loadKnowledge = async () => {
    setLoading(true)
    try {
      const data = await knowledgeApi.list(filter || undefined)
      setKnowledge(data)
    } catch (error) {
      console.error('Failed to load knowledge:', error)
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setIsSearching(true)
    try {
      const results = await searchApi.search(searchQuery, ['knowledge', 'chapters', 'ideas'], true)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    }
    setIsSearching(false)
  }

  const handleCreate = async () => {
    try {
      await knowledgeApi.create({
        source_type: formData.source_type,
        title: formData.title,
        content: formData.content,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
      })
      setIsCreating(false)
      setFormData({ source_type: 'document', title: '', content: '', tags: '' })
      loadKnowledge()
    } catch (error) {
      console.error('Failed to create:', error)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this?')) return
    try {
      await knowledgeApi.delete(id)
      loadKnowledge()
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'chat': return MessageSquare
      case 'document': return FileText
      default: return Database
    }
  }

  const getSourceColor = (type: string) => {
    switch (type) {
      case 'chat': return 'bg-blue-500/10 text-blue-400'
      case 'document': return 'bg-green-500/10 text-green-400'
      default: return 'bg-primary/10 text-primary'
    }
  }

  const getVerificationBadge = (status?: string, autoExtracted?: boolean) => {
    if (status === 'pending') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-xs">
          <Clock className="w-3 h-3" />
          Pending
        </span>
      )
    }
    if (autoExtracted) {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-xs">
          <Sparkles className="w-3 h-3" />
          Auto
        </span>
      )
    }
    return (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-xs">
        <CheckCircle className="w-3 h-3" />
        Approved
      </span>
    )
  }

  const tabs = [
    { id: 'knowledge' as Tab, label: 'Knowledge Base', icon: Database, count: knowledge.length },
    { id: 'characters' as Tab, label: 'Characters', icon: Users, count: characters.length },
    { id: 'world_rules' as Tab, label: 'World Rules', icon: Globe, count: worldRules.length },
    { id: 'foreshadowing' as Tab, label: 'Foreshadowing', icon: Sparkles, count: foreshadowing.length },
    { id: 'facts' as Tab, label: 'Story Facts', icon: Lightbulb, count: facts.length },
  ]

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-display font-semibold text-foreground">
              Knowledge Base
            </h1>
            <p className="text-muted-foreground">
              Your saved knowledge and story elements
            </p>
          </div>
          
          {/* Series Selector */}
          {seriesList.length > 0 && activeTab !== 'knowledge' && (
            <div className="flex items-center gap-2 ml-4 p-2 bg-card rounded-lg border border-border">
              <Library className="w-4 h-4 text-muted-foreground" />
              <select
                value={selectedSeriesId || ''}
                onChange={(e) => setSelectedSeriesId(Number(e.target.value))}
                className="bg-transparent border-none text-sm focus:outline-none"
              >
                {seriesList.map(s => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
            </div>
          )}
          
          {/* Pending Badge */}
          {pendingCount > 0 && (
            <a 
              href="/verification"
              className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors"
            >
              <Clock className="w-4 h-4" />
              {pendingCount} pending review
            </a>
          )}
        </div>
        
        {activeTab === 'knowledge' && (
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span className="font-medium">Add Knowledge</span>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Verification Filter (for story elements) */}
      {activeTab !== 'knowledge' && (
        <div className="flex gap-2 mb-4">
          {['approved', 'pending', null].map((status) => (
            <button
              key={status || 'all'}
              onClick={() => setVerificationFilter(status)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                verificationFilter === status
                  ? status === 'pending' 
                    ? "bg-yellow-500/20 text-yellow-400"
                    : status === 'approved'
                    ? "bg-green-500/20 text-green-400"
                    : "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              {status === 'approved' && <CheckCircle className="w-3 h-3" />}
              {status === 'pending' && <Clock className="w-3 h-3" />}
              {status === null ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      )}

      {/* Search bar (for knowledge tab) */}
      {activeTab === 'knowledge' && (
        <>
          <div className="flex gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search across all content..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={isSearching}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isSearching ? 'Searching...' : 'Search'}
            </button>
          </div>

          {/* Search Results */}
          <AnimatePresence>
            {searchResults && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mb-6 p-4 rounded-xl bg-card border border-primary/30"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-medium text-foreground">
                    Search Results ({searchResults.total_results})
                  </h3>
                  <button
                    onClick={() => setSearchResults(null)}
                    className="p-1 hover:bg-muted rounded"
                  >
                    <X className="w-4 h-4 text-muted-foreground" />
                  </button>
                </div>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {Object.entries(searchResults.results).map(([collection, items]) => (
                    items.length > 0 && (
                      <div key={collection}>
                        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                          {collection}
                        </p>
                        {(items as Array<Record<string, unknown>>).map((item, index) => (
                          <div key={index} className="p-2 rounded bg-muted/50 mb-1">
                            <p className="text-sm font-medium text-foreground">
                              {(item.title as string) || 'Untitled'}
                            </p>
                            <p className="text-xs text-muted-foreground line-clamp-1">
                              {(item.content as string)?.slice(0, 100)}...
                            </p>
                          </div>
                        ))}
                      </div>
                    )
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Type Filters */}
          <div className="flex gap-2 mb-6">
            {[null, 'chat', 'document', 'idea'].map((type) => (
              <button
                key={type || 'all'}
                onClick={() => setFilter(type)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  filter === type
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                {type === null ? 'All' : type.charAt(0).toUpperCase() + type.slice(1)}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Create Form */}
      <AnimatePresence>
        {isCreating && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-card border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">Add Knowledge</h3>
              <button
                onClick={() => setIsCreating(false)}
                className="p-1 hover:bg-muted rounded"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="flex gap-4">
                <select
                  value={formData.source_type}
                  onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="document">Document</option>
                  <option value="idea">Idea</option>
                </select>
                <input
                  type="text"
                  placeholder="Title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <textarea
                placeholder="Content..."
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                rows={6}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
              />
              <input
                type="text"
                placeholder="Tags (comma separated)"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
              <button
                onClick={handleCreate}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Save Knowledge
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : activeTab === 'knowledge' ? (
          /* Knowledge Grid */
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {knowledge.map((item) => {
              const Icon = getSourceIcon(item.source_type)
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-4 rounded-xl bg-card border border-border hover:border-primary/30 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className={cn("flex items-center gap-1.5 px-2 py-0.5 rounded text-xs", getSourceColor(item.source_type))}>
                      <Icon className="w-3 h-3" />
                      {item.source_type}
                    </div>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-1 hover:bg-destructive/20 rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-destructive" />
                    </button>
                  </div>
                  <h3 className="font-medium text-foreground mb-1">
                    {item.title || 'Untitled'}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                    {item.content}
                  </p>
                  {item.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {item.tags.map((tag) => (
                        <span key={tag} className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {formatDate(item.created_at)}
                  </p>
                </motion.div>
              )
            })}
            {knowledge.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No knowledge entries yet</p>
              </div>
            )}
          </div>
        ) : activeTab === 'characters' ? (
          /* Characters Grid */
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {characters.map((char) => (
              <motion.div
                key={char.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-blue-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-400" />
                    <h3 className="font-medium text-foreground">{char.name}</h3>
                  </div>
                  {getVerificationBadge(char.verification_status, char.auto_extracted)}
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3 mb-2">
                  {char.description || char.personality || 'No description'}
                </p>
                {char.first_appearance_chapter && (
                  <p className="text-xs text-muted-foreground">
                    First appears: Chapter {char.first_appearance_chapter}
                  </p>
                )}
              </motion.div>
            ))}
            {characters.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No characters found</p>
              </div>
            )}
          </div>
        ) : activeTab === 'world_rules' ? (
          /* World Rules Grid */
          <div className="grid gap-4 md:grid-cols-2">
            {worldRules.map((rule) => (
              <motion.div
                key={rule.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-green-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-green-400" />
                    <span className="px-2 py-0.5 rounded bg-green-500/10 text-green-400 text-xs">
                      {rule.rule_category}
                    </span>
                  </div>
                  {getVerificationBadge(rule.verification_status, rule.auto_extracted)}
                </div>
                <h3 className="font-medium text-foreground mb-1">{rule.rule_name}</h3>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {rule.rule_description}
                </p>
              </motion.div>
            ))}
            {worldRules.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Globe className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No world rules found</p>
              </div>
            )}
          </div>
        ) : activeTab === 'foreshadowing' ? (
          /* Foreshadowing Grid */
          <div className="grid gap-4 md:grid-cols-2">
            {foreshadowing.map((seed) => (
              <motion.div
                key={seed.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={cn(
                  "p-4 rounded-xl border transition-colors",
                  seed.status === 'paid_off' 
                    ? "bg-green-500/5 border-green-500/30" 
                    : "bg-card border-border hover:border-purple-500/30"
                )}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs">
                      {seed.seed_type}
                    </span>
                    {seed.status === 'paid_off' && (
                      <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-xs">
                        Paid Off
                      </span>
                    )}
                  </div>
                  {getVerificationBadge(seed.verification_status, seed.auto_extracted)}
                </div>
                <h3 className="font-medium text-foreground mb-1">{seed.title}</h3>
                <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                  {seed.planted_text}
                </p>
                {seed.intended_payoff && (
                  <p className="text-xs text-muted-foreground italic">
                    → {seed.intended_payoff}
                  </p>
                )}
              </motion.div>
            ))}
            {foreshadowing.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No foreshadowing found</p>
              </div>
            )}
          </div>
        ) : (
          /* Facts Grid */
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {facts.map((fact) => (
              <motion.div
                key={fact.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-yellow-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-yellow-400" />
                    <span className="px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 text-xs">
                      {fact.fact_category}
                    </span>
                    {fact.is_secret && (
                      <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 text-xs">
                        Secret
                      </span>
                    )}
                  </div>
                  {getVerificationBadge(fact.verification_status, fact.auto_extracted)}
                </div>
                <p className="text-sm text-foreground">
                  {fact.fact_description}
                </p>
              </motion.div>
            ))}
            {facts.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Lightbulb className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No story facts found</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
