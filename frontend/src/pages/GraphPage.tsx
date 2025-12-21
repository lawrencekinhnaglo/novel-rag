import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, Users, MapPin, Calendar, Network, 
  ChevronRight, X, Search, Link2 
} from 'lucide-react'
import { 
  graphApi, 
  type Character, 
  type Location, 
  type TimelineEvent 
} from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

type Tab = 'characters' | 'locations' | 'timeline'

export function GraphPage() {
  const [activeTab, setActiveTab] = useState<Tab>('characters')
  const [characters, setCharacters] = useState<Character[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)
  
  const [isCreating, setIsCreating] = useState(false)
  const [isCreatingRelationship, setIsCreatingRelationship] = useState(false)
  const [formData, setFormData] = useState({
    name: '', description: '', 
    event_id: '', title: '', timestamp: '', chapter: '',
    char1: '', char2: '', relType: ''
  })

  useEffect(() => {
    loadData()
  }, [])

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

  const tabs = [
    { id: 'characters' as Tab, label: 'Characters', icon: Users, count: characters.length },
    { id: 'locations' as Tab, label: 'Locations', icon: MapPin, count: locations.length },
    { id: 'timeline' as Tab, label: 'Timeline', icon: Calendar, count: events.length },
  ]

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-semibold text-foreground">
            Story Graph
          </h1>
          <p className="text-muted-foreground">
            Characters, locations, and timeline in Neo4j
          </p>
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
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span className="font-medium">Add {activeTab.slice(0, -1)}</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors",
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
        ) : (
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
        )}
      </div>
    </div>
  )
}

