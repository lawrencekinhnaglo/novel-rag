import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Calendar, Plus, Trash2, Edit2, Save, X, Loader2,
  MapPin, Users, BookOpen, AlertTriangle, Clock
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { timelineApi, storyApi, type TimelineEventEnhanced, type Series } from '@/lib/api'

export function TimelinePage() {
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [events, setEvents] = useState<TimelineEventEnhanced[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isAddingEvent, setIsAddingEvent] = useState(false)
  const [editingEventId, setEditingEventId] = useState<number | null>(null)
  const [gaps, setGaps] = useState<Array<{ between_events: string[]; gap_size: number }>>([])
  
  // Form state
  const [formData, setFormData] = useState({
    event_name: '',
    event_description: '',
    story_date: '',
    story_date_sortable: 0,
    location: '',
    event_type: 'plot',
    importance: 'normal'
  })

  useEffect(() => {
    loadSeries()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadEvents()
    }
  }, [selectedSeriesId])

  const loadSeries = async () => {
    try {
      const data = await storyApi.listSeries()
      setSeries(data)
      if (data.length > 0) {
        setSelectedSeriesId(data[0].id)
      }
    } catch (error) {
      console.error('Failed to load series:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadEvents = async () => {
    if (!selectedSeriesId) return
    try {
      const [eventsData, gapsData] = await Promise.all([
        timelineApi.getTimeline(selectedSeriesId),
        timelineApi.findGaps(selectedSeriesId)
      ])
      setEvents(eventsData)
      setGaps(gapsData.gaps)
    } catch (error) {
      console.error('Failed to load events:', error)
    }
  }

  const handleCreateEvent = async () => {
    if (!selectedSeriesId || !formData.event_name) return
    try {
      await timelineApi.createEvent({
        series_id: selectedSeriesId,
        ...formData
      })
      await loadEvents()
      setIsAddingEvent(false)
      resetForm()
    } catch (error) {
      console.error('Failed to create event:', error)
    }
  }

  const handleUpdateEvent = async (eventId: number) => {
    try {
      await timelineApi.updateEvent(eventId, formData)
      await loadEvents()
      setEditingEventId(null)
      resetForm()
    } catch (error) {
      console.error('Failed to update event:', error)
    }
  }

  const handleDeleteEvent = async (eventId: number) => {
    try {
      await timelineApi.deleteEvent(eventId)
      setEvents(events.filter(e => e.id !== eventId))
    } catch (error) {
      console.error('Failed to delete event:', error)
    }
  }

  const startEdit = (event: TimelineEventEnhanced) => {
    setEditingEventId(event.id)
    setFormData({
      event_name: event.event_name,
      event_description: event.event_description || '',
      story_date: event.story_date || '',
      story_date_sortable: event.story_date_sortable || 0,
      location: event.location || '',
      event_type: event.event_type,
      importance: event.importance
    })
  }

  const resetForm = () => {
    setFormData({
      event_name: '',
      event_description: '',
      story_date: '',
      story_date_sortable: 0,
      location: '',
      event_type: 'plot',
      importance: 'normal'
    })
  }

  const getEventTypeColor = (type: string) => {
    switch (type) {
      case 'plot': return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
      case 'character': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'world': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-muted text-muted-foreground border-border'
    }
  }

  const getImportanceStyle = (importance: string) => {
    switch (importance) {
      case 'critical': return 'border-l-4 border-l-red-500'
      case 'major': return 'border-l-4 border-l-orange-500'
      case 'normal': return 'border-l-4 border-l-blue-500'
      default: return 'border-l-4 border-l-gray-500'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 p-6 border-b border-border bg-gradient-to-r from-blue-900/20 to-cyan-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20">
              <Calendar className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">Timeline</h1>
              <p className="text-muted-foreground">Track and visualize story events in chronological order</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <select
              value={selectedSeriesId || ''}
              onChange={(e) => setSelectedSeriesId(Number(e.target.value))}
              className="bg-card border border-border rounded-lg px-4 py-2"
            >
              <option value="">Select series...</option>
              {series.map(s => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
            
            <button
              onClick={() => setIsAddingEvent(true)}
              disabled={!selectedSeriesId}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Event
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* Gaps Warning */}
        {gaps.length > 0 && (
          <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-400 mb-2">
              <AlertTriangle className="w-5 h-5" />
              <span className="font-medium">Timeline Gaps Detected</span>
            </div>
            <div className="space-y-1 text-sm text-yellow-300/80">
              {gaps.map((gap, i) => (
                <p key={i}>
                  Gap of {gap.gap_size} units between "{gap.between_events[0]}" and "{gap.between_events[1]}"
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Add Event Form */}
        {isAddingEvent && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 bg-card border border-border rounded-xl p-6"
          >
            <h3 className="text-lg font-semibold mb-4">Add New Event</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-sm text-muted-foreground mb-1">Event Name *</label>
                <input
                  type="text"
                  value={formData.event_name}
                  onChange={(e) => setFormData({ ...formData, event_name: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="What happened?"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-muted-foreground mb-1">Description</label>
                <textarea
                  value={formData.event_description}
                  onChange={(e) => setFormData({ ...formData, event_description: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2 resize-none"
                  rows={2}
                  placeholder="Describe the event in detail..."
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Story Date</label>
                <input
                  type="text"
                  value={formData.story_date}
                  onChange={(e) => setFormData({ ...formData, story_date: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="e.g., Year 1, Day 45"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Sort Order (numeric)</label>
                <input
                  type="number"
                  value={formData.story_date_sortable}
                  onChange={(e) => setFormData({ ...formData, story_date_sortable: Number(e.target.value) })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Location</label>
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="Where did it happen?"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Event Type</label>
                <select
                  value={formData.event_type}
                  onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                >
                  <option value="plot">Plot</option>
                  <option value="character">Character</option>
                  <option value="world">World</option>
                  <option value="background">Background</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Importance</label>
                <select
                  value={formData.importance}
                  onChange={(e) => setFormData({ ...formData, importance: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                >
                  <option value="minor">Minor</option>
                  <option value="normal">Normal</option>
                  <option value="major">Major</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => { setIsAddingEvent(false); resetForm() }}
                className="px-4 py-2 border border-border rounded-lg hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateEvent}
                disabled={!formData.event_name}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg disabled:opacity-50 flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save Event
              </button>
            </div>
          </motion.div>
        )}

        {/* Timeline */}
        {!selectedSeriesId ? (
          <div className="text-center text-muted-foreground py-12">
            <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Select a series to view its timeline</p>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center text-muted-foreground py-12 border border-dashed border-border rounded-lg">
            <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No events yet. Add your first event above!</p>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-border" />
            
            <div className="space-y-4">
              {events.map((event, index) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    "relative pl-20 pr-4",
                  )}
                >
                  {/* Timeline dot */}
                  <div className="absolute left-6 w-4 h-4 rounded-full bg-blue-500 border-4 border-background" />
                  
                  <div className={cn(
                    "bg-card border border-border rounded-lg p-4",
                    getImportanceStyle(event.importance)
                  )}>
                    {editingEventId === event.id ? (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={formData.event_name}
                          onChange={(e) => setFormData({ ...formData, event_name: e.target.value })}
                          className="w-full bg-muted border border-border rounded-lg px-3 py-2 font-medium"
                        />
                        <textarea
                          value={formData.event_description}
                          onChange={(e) => setFormData({ ...formData, event_description: e.target.value })}
                          className="w-full bg-muted border border-border rounded-lg px-3 py-2 resize-none"
                          rows={2}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleUpdateEvent(event.id)}
                            className="px-3 py-1 bg-blue-500 text-white rounded-lg text-sm flex items-center gap-1"
                          >
                            <Save className="w-3 h-3" /> Save
                          </button>
                          <button
                            onClick={() => { setEditingEventId(null); resetForm() }}
                            className="px-3 py-1 border border-border rounded-lg text-sm flex items-center gap-1"
                          >
                            <X className="w-3 h-3" /> Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="font-semibold">{event.event_name}</h3>
                              <span className={cn(
                                "px-2 py-0.5 rounded-full text-xs border",
                                getEventTypeColor(event.event_type)
                              )}>
                                {event.event_type}
                              </span>
                            </div>
                            {event.story_date && (
                              <p className="text-sm text-muted-foreground flex items-center gap-1">
                                <Calendar className="w-3 h-3" /> {event.story_date}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => startEdit(event)}
                              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteEvent(event.id)}
                              className="p-1.5 hover:bg-red-500/20 rounded-lg text-muted-foreground hover:text-red-400"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                        
                        {event.event_description && (
                          <p className="text-sm mt-2">{event.event_description}</p>
                        )}
                        
                        <div className="flex flex-wrap gap-3 mt-3 text-xs text-muted-foreground">
                          {event.location && (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" /> {event.location}
                            </span>
                          )}
                          {event.character_names && event.character_names.length > 0 && (
                            <span className="flex items-center gap-1">
                              <Users className="w-3 h-3" /> {event.character_names.join(', ')}
                            </span>
                          )}
                          {event.chapter_title && (
                            <span className="flex items-center gap-1">
                              <BookOpen className="w-3 h-3" /> {event.chapter_title}
                            </span>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}





