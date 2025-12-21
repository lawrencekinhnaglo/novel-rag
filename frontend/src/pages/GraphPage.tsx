import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, Users, MapPin, Calendar, Network, 
  ChevronRight, X, Link2, Library, Sparkles, Globe,
  ArrowRight, CheckCircle, Clock, Target
} from 'lucide-react'
import { 
  graphApi, storyApi,
  type Character, 
  type Location, 
  type TimelineEvent,
  type Series
} from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

type Tab = 'characters' | 'locations' | 'timeline' | 'foreshadowing' | 'world_rules'

interface Foreshadowing {
  id: number
  title: string
  planted_text: string
  planted_book?: number
  planted_chapter?: number
  payoff_book?: number
  payoff_chapter?: number
  payoff_text?: string
  seed_type: string
  subtlety: number
  status: string
  intended_payoff?: string
  verification_status?: string
}

interface WorldRule {
  id: number
  rule_name: string
  rule_category: string
  rule_description: string
  exceptions?: string[]
  is_hard_rule: boolean
  source_chapter?: number
  verification_status?: string
}

export function GraphPage() {
  const [activeTab, setActiveTab] = useState<Tab>('characters')
  const [characters, setCharacters] = useState<Character[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [foreshadowing, setForeshadowing] = useState<Foreshadowing[]>([])
  const [worldRules, setWorldRules] = useState<WorldRule[]>([])
  const [loading, setLoading] = useState(true)
  
  // Series selection
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  
  const [isCreating, setIsCreating] = useState(false)
  const [isCreatingRelationship, setIsCreatingRelationship] = useState(false)
  const [formData, setFormData] = useState({
    name: '', description: '', 
    event_id: '', title: '', timestamp: '', chapter: '',
    char1: '', char2: '', relType: ''
  })

  useEffect(() => {
    loadSeriesList()
  }, [])

  useEffect(() => {
    loadData()
  }, [selectedSeriesId])

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

  const loadData = async () => {
    setLoading(true)
    try {
      const [charsData, locsData, eventsData] = await Promise.all([
        graphApi.getCharacters(),
        graphApi.getLocations(),
        graphApi.getTimeline()
      ])
      setCharacters(charsData.characters)
      setLocations(locsData.locations)
      setEvents(eventsData.events)
      
      // Load foreshadowing and world rules if series selected
      if (selectedSeriesId) {
        const [fsData, rulesData] = await Promise.all([
          fetch(`${API_BASE}/story/foreshadowing/${selectedSeriesId}?status=approved`).then(r => r.json()),
          fetch(`${API_BASE}/story/world-rules/${selectedSeriesId}?status=approved`).then(r => r.json())
        ])
        setForeshadowing(fsData)
        setWorldRules(rulesData)
      }
    } catch (error) {
      console.error('Failed to load graph data:', error)
    }
    setLoading(false)
  }

  const handleCreateCharacter = async () => {
    try {
      await graphApi.createCharacter({
        name: formData.name,
        description: formData.description
      })
      setIsCreating(false)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to create character:', error)
    }
  }

  const handleCreateLocation = async () => {
    try {
      await graphApi.createLocation({
        name: formData.name,
        description: formData.description
      })
      setIsCreating(false)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to create location:', error)
    }
  }

  const handleCreateEvent = async () => {
    try {
      await graphApi.createEvent({
        event_id: formData.event_id || `event_${Date.now()}`,
        title: formData.title,
        description: formData.description,
        timestamp: formData.timestamp || undefined,
        chapter: formData.chapter ? parseInt(formData.chapter) : undefined
      })
      setIsCreating(false)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to create event:', error)
    }
  }

  const handleCreateRelationship = async () => {
    try {
      await graphApi.createRelationship({
        character1: formData.char1,
        character2: formData.char2,
        relationship_type: formData.relType
      })
      setIsCreatingRelationship(false)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to create relationship:', error)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '', description: '',
      event_id: '', title: '', timestamp: '', chapter: '',
      char1: '', char2: '', relType: ''
    })
  }

  const getSubtletyLabel = (level: number) => {
    const labels = ['Very Obvious', 'Obvious', 'Moderate', 'Subtle', 'Very Subtle']
    return labels[level - 1] || 'Unknown'
  }

  const tabs = [
    { id: 'characters' as Tab, label: 'Characters', icon: Users, count: characters.length },
    { id: 'locations' as Tab, label: 'Locations', icon: MapPin, count: locations.length },
    { id: 'timeline' as Tab, label: 'Timeline', icon: Calendar, count: events.length },
    { id: 'foreshadowing' as Tab, label: 'Foreshadowing', icon: Sparkles, count: foreshadowing.length },
    { id: 'world_rules' as Tab, label: 'World Rules', icon: Globe, count: worldRules.length },
  ]

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-display font-semibold text-foreground">
              Story Graph
            </h1>
            <p className="text-muted-foreground">
              Visualize your story's structure
            </p>
          </div>
          
          {/* Series Selector */}
          {seriesList.length > 0 && (
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
        </div>
        
        <div className="flex gap-2">
          {activeTab === 'characters' && (
            <button
              onClick={() => setIsCreatingRelationship(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent transition-colors"
            >
              <Link2 className="w-4 h-4" />
              <span className="font-medium">Add Relationship</span>
            </button>
          )}
          {(activeTab === 'characters' || activeTab === 'locations' || activeTab === 'timeline') && (
            <button
              onClick={() => setIsCreating(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span className="font-medium">
                Add {activeTab === 'characters' ? 'Character' : activeTab === 'locations' ? 'Location' : 'Event'}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
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
              {tab.label} ({tab.count})
            </button>
          )
        })}
      </div>

      {/* Create Forms */}
      <AnimatePresence>
        {isCreating && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-card border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">
                Add {activeTab === 'characters' ? 'Character' : activeTab === 'locations' ? 'Location' : 'Event'}
              </h3>
              <button onClick={() => { setIsCreating(false); resetForm() }} className="p-1 hover:bg-muted rounded">
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-4">
              {activeTab === 'timeline' ? (
                <>
                  <div className="flex gap-4">
                    <input
                      type="text"
                      placeholder="Event Title"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    />
                    <input
                      type="number"
                      placeholder="Chapter"
                      value={formData.chapter}
                      onChange={(e) => setFormData({ ...formData, chapter: e.target.value })}
                      className="w-28 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="Story Timestamp (e.g., 'Day 1', 'Year 2045')"
                    value={formData.timestamp}
                    onChange={(e) => setFormData({ ...formData, timestamp: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                  />
                </>
              ) : (
                <input
                  type="text"
                  placeholder="Name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                />
              )}
              <textarea
                placeholder="Description..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
              />
              <button
                onClick={() => {
                  if (activeTab === 'characters') handleCreateCharacter()
                  else if (activeTab === 'locations') handleCreateLocation()
                  else handleCreateEvent()
                }}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Create
              </button>
            </div>
          </motion.div>
        )}

        {isCreatingRelationship && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-card border border-accent/30"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">Create Relationship</h3>
              <button onClick={() => { setIsCreatingRelationship(false); resetForm() }} className="p-1 hover:bg-muted rounded">
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="flex gap-4 items-center">
              <select
                value={formData.char1}
                onChange={(e) => setFormData({ ...formData, char1: e.target.value })}
                className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
              >
                <option value="">Select Character 1</option>
                {characters.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Relationship (e.g., LOVES, HATES)"
                value={formData.relType}
                onChange={(e) => setFormData({ ...formData, relType: e.target.value })}
                className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
              <select
                value={formData.char2}
                onChange={(e) => setFormData({ ...formData, char2: e.target.value })}
                className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
              >
                <option value="">Select Character 2</option>
                {characters.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
              <button
                onClick={handleCreateRelationship}
                className="px-4 py-2 rounded-lg bg-accent text-accent-foreground hover:bg-accent/90 transition-colors"
              >
                Create
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : activeTab === 'characters' ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {characters.map((char) => (
              <motion.div
                key={char.name}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-primary/30 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                    <Users className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="font-display font-semibold text-foreground">{char.name}</h3>
                </div>
                {char.description && (
                  <p className="text-sm text-muted-foreground mb-3">{char.description}</p>
                )}
                {char.relationships && char.relationships.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Relationships</p>
                    {char.relationships.map((rel, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="text-primary">{rel.type}</span>
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <span className="text-foreground">{rel.target}</span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
            {characters.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No characters yet. Create your first character!</p>
              </div>
            )}
          </div>
        ) : activeTab === 'locations' ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {locations.map((loc) => (
              <motion.div
                key={loc.name}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-accent/30 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
                    <MapPin className="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <h3 className="font-display font-semibold text-foreground">{loc.name}</h3>
                    {loc.event_count !== undefined && (
                      <p className="text-xs text-muted-foreground">{loc.event_count} events</p>
                    )}
                  </div>
                </div>
                {loc.description && (
                  <p className="text-sm text-muted-foreground">{loc.description}</p>
                )}
              </motion.div>
            ))}
            {locations.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <MapPin className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No locations yet. Create your first location!</p>
              </div>
            )}
          </div>
        ) : activeTab === 'timeline' ? (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
            
            <div className="space-y-6">
              {events.map((event, index) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="relative pl-16"
                >
                  {/* Timeline dot */}
                  <div className="absolute left-4 w-5 h-5 rounded-full bg-primary/20 border-2 border-primary flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-primary" />
                  </div>
                  
                  <div className="p-4 rounded-xl bg-card border border-border">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-display font-semibold text-foreground">{event.title}</h3>
                      <div className="flex gap-2">
                        {event.chapter && (
                          <span className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs">
                            Ch. {event.chapter}
                          </span>
                        )}
                        {event.story_timestamp && (
                          <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                            {event.story_timestamp}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">{event.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {event.characters?.map((char) => (
                        <span key={char} className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs">
                          {char}
                        </span>
                      ))}
                      {event.locations?.map((loc) => (
                        <span key={loc} className="px-2 py-0.5 rounded bg-accent/10 text-accent text-xs">
                          📍 {loc}
                        </span>
                      ))}
                    </div>
                  </div>
                </motion.div>
              ))}
              {events.length === 0 && (
                <div className="text-center py-12 text-muted-foreground pl-16">
                  <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No timeline events yet. Create your first event!</p>
                </div>
              )}
            </div>
          </div>
        ) : activeTab === 'foreshadowing' ? (
          /* Foreshadowing Visualization */
          <div className="space-y-6">
            {/* Seeds grouped by status */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Planted Seeds */}
              <div>
                <h3 className="flex items-center gap-2 text-lg font-medium text-foreground mb-4">
                  <Clock className="w-5 h-5 text-yellow-400" />
                  Planted Seeds ({foreshadowing.filter(f => f.status === 'planted').length})
                </h3>
                <div className="space-y-3">
                  {foreshadowing.filter(f => f.status === 'planted').map((seed) => (
                    <motion.div
                      key={seed.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="p-4 rounded-xl bg-yellow-500/5 border border-yellow-500/20"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-foreground">{seed.title}</h4>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs">
                            {seed.seed_type}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                            {getSubtletyLabel(seed.subtlety)}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2 italic">
                        "{seed.planted_text}"
                      </p>
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Planted: Ch. {seed.planted_chapter || '?'}</span>
                        {seed.intended_payoff && (
                          <span className="flex items-center gap-1 text-purple-400">
                            <Target className="w-3 h-3" />
                            {seed.intended_payoff}
                          </span>
                        )}
                      </div>
                    </motion.div>
                  ))}
                  {foreshadowing.filter(f => f.status === 'planted').length === 0 && (
                    <p className="text-muted-foreground text-center py-6">No planted seeds</p>
                  )}
                </div>
              </div>

              {/* Paid Off Seeds */}
              <div>
                <h3 className="flex items-center gap-2 text-lg font-medium text-foreground mb-4">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  Paid Off ({foreshadowing.filter(f => f.status === 'paid_off').length})
                </h3>
                <div className="space-y-3">
                  {foreshadowing.filter(f => f.status === 'paid_off').map((seed) => (
                    <motion.div
                      key={seed.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="p-4 rounded-xl bg-green-500/5 border border-green-500/20"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-foreground">{seed.title}</h4>
                        <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs">
                          {seed.seed_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-sm mb-2">
                        <div className="flex-1 p-2 bg-yellow-500/5 rounded text-yellow-400/80">
                          <p className="text-xs text-muted-foreground">Planted Ch. {seed.planted_chapter}</p>
                          <p className="italic">"{seed.planted_text?.slice(0, 60)}..."</p>
                        </div>
                        <ArrowRight className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 p-2 bg-green-500/5 rounded text-green-400/80">
                          <p className="text-xs text-muted-foreground">Payoff Ch. {seed.payoff_chapter}</p>
                          <p className="italic">"{seed.payoff_text?.slice(0, 60)}..."</p>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                  {foreshadowing.filter(f => f.status === 'paid_off').length === 0 && (
                    <p className="text-muted-foreground text-center py-6">No paid off seeds yet</p>
                  )}
                </div>
              </div>
            </div>
            
            {foreshadowing.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No foreshadowing elements yet.</p>
                <p className="text-sm mt-2">
                  Foreshadowing is auto-extracted from chapters or can be added in Story Manager.
                </p>
              </div>
            )}
          </div>
        ) : (
          /* World Rules */
          <div className="space-y-6">
            {/* Group by category */}
            {['magic', 'technology', 'society', 'geography', 'biology', 'other'].map((category) => {
              const categoryRules = worldRules.filter(r => r.rule_category === category)
              if (categoryRules.length === 0) return null
              
              return (
                <div key={category}>
                  <h3 className="flex items-center gap-2 text-lg font-medium text-foreground mb-4 capitalize">
                    <Globe className="w-5 h-5 text-green-400" />
                    {category} Rules ({categoryRules.length})
                  </h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {categoryRules.map((rule) => (
                      <motion.div
                        key={rule.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className={cn(
                          "p-4 rounded-xl border",
                          rule.is_hard_rule 
                            ? "bg-red-500/5 border-red-500/20" 
                            : "bg-green-500/5 border-green-500/20"
                        )}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-foreground">{rule.rule_name}</h4>
                          <span className={cn(
                            "px-2 py-0.5 rounded text-xs",
                            rule.is_hard_rule 
                              ? "bg-red-500/20 text-red-400" 
                              : "bg-yellow-500/20 text-yellow-400"
                          )}>
                            {rule.is_hard_rule ? 'Hard Rule' : 'Soft Rule'}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">
                          {rule.rule_description}
                        </p>
                        {rule.exceptions && rule.exceptions.length > 0 && (
                          <div className="text-xs">
                            <span className="text-muted-foreground">Exceptions: </span>
                            <span className="text-yellow-400">{rule.exceptions.join(', ')}</span>
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                </div>
              )
            })}
            
            {worldRules.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <Globe className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No world rules defined yet.</p>
                <p className="text-sm mt-2">
                  World rules are auto-extracted from chapters or can be added in Story Manager.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
