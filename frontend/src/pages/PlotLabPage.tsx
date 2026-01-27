import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Sparkles, Plus, Trash2, ChevronDown, ChevronRight, 
  Wand2, BookOpen, AlertCircle, Check, Loader2,
  GitBranch, HelpCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { plotApi, storyApi, type PlotTemplate, type PlotBeat, type PlotVariation, type Series } from '@/lib/api'

export function PlotLabPage() {
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [templates, setTemplates] = useState<PlotTemplate[]>([])
  const [beats, setBeats] = useState<PlotBeat[]>([])
  const [variations, setVariations] = useState<PlotVariation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'beats' | 'whatif'>('beats')
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<string>('Three-Act Structure')
  const [expandedBeats, setExpandedBeats] = useState<Set<number>>(new Set())
  
  // What-If form state
  const [whatIfTitle, setWhatIfTitle] = useState('')
  const [whatIfPremise, setWhatIfPremise] = useState('')
  const [isCreatingWhatIf, setIsCreatingWhatIf] = useState(false)

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadSeriesData()
    }
  }, [selectedSeriesId])

  const loadInitialData = async () => {
    try {
      const [seriesList, templatesList] = await Promise.all([
        storyApi.listSeries(),
        plotApi.getTemplates()
      ])
      setSeries(seriesList)
      setTemplates(templatesList)
      if (seriesList.length > 0) {
        setSelectedSeriesId(seriesList[0].id)
      }
    } catch (error) {
      console.error('Failed to load initial data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadSeriesData = async () => {
    if (!selectedSeriesId) return
    try {
      const [beatsData, variationsData] = await Promise.all([
        plotApi.getBeats(selectedSeriesId),
        plotApi.getVariations(selectedSeriesId)
      ])
      setBeats(beatsData)
      setVariations(variationsData)
    } catch (error) {
      console.error('Failed to load series data:', error)
    }
  }

  const handleGenerateBeatSheet = async () => {
    if (!selectedSeriesId) return
    setIsGenerating(true)
    try {
      await plotApi.generateBeatSheet({
        series_id: selectedSeriesId,
        template_name: selectedTemplate
      })
      await loadSeriesData()
    } catch (error) {
      console.error('Failed to generate beat sheet:', error)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDeleteBeat = async (beatId: number) => {
    try {
      await plotApi.deleteBeat(beatId)
      setBeats(beats.filter(b => b.id !== beatId))
    } catch (error) {
      console.error('Failed to delete beat:', error)
    }
  }

  const handleUpdateBeatStatus = async (beatId: number, status: string) => {
    try {
      await plotApi.updateBeat(beatId, { status })
      setBeats(beats.map(b => b.id === beatId ? { ...b, status } : b))
    } catch (error) {
      console.error('Failed to update beat:', error)
    }
  }

  const handleCreateWhatIf = async () => {
    if (!selectedSeriesId || !whatIfTitle || !whatIfPremise) return
    setIsCreatingWhatIf(true)
    try {
      const result = await plotApi.createWhatIf({
        series_id: selectedSeriesId,
        variation_title: whatIfTitle,
        what_if_premise: whatIfPremise
      })
      await loadSeriesData()
      setWhatIfTitle('')
      setWhatIfPremise('')
    } catch (error) {
      console.error('Failed to create what-if:', error)
    } finally {
      setIsCreatingWhatIf(false)
    }
  }

  const handleDeleteVariation = async (variationId: number) => {
    try {
      await plotApi.deleteVariation(variationId)
      setVariations(variations.filter(v => v.id !== variationId))
    } catch (error) {
      console.error('Failed to delete variation:', error)
    }
  }

  const toggleBeatExpanded = (beatId: number) => {
    const newExpanded = new Set(expandedBeats)
    if (newExpanded.has(beatId)) {
      newExpanded.delete(beatId)
    } else {
      newExpanded.add(beatId)
    }
    setExpandedBeats(newExpanded)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'drafted': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      default: return 'bg-muted text-muted-foreground border-border'
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'major': return 'text-red-400'
      case 'moderate': return 'text-yellow-400'
      default: return 'text-blue-400'
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
      <div className="flex-shrink-0 p-6 border-b border-border bg-gradient-to-r from-purple-900/20 to-pink-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Sparkles className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">Plot Lab</h1>
              <p className="text-muted-foreground">Structure your story with beat sheets and explore alternatives</p>
            </div>
          </div>
          
          {/* Series Selector */}
          <select
            value={selectedSeriesId || ''}
            onChange={(e) => setSelectedSeriesId(Number(e.target.value))}
            className="bg-card border border-border rounded-lg px-4 py-2 text-foreground"
          >
            <option value="">Select a series...</option>
            {series.map(s => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => setActiveTab('beats')}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors",
              activeTab === 'beats' 
                ? "bg-purple-500 text-white" 
                : "bg-muted text-muted-foreground hover:text-foreground"
            )}
          >
            <BookOpen className="w-4 h-4 inline mr-2" />
            Beat Sheet
          </button>
          <button
            onClick={() => setActiveTab('whatif')}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors",
              activeTab === 'whatif' 
                ? "bg-purple-500 text-white" 
                : "bg-muted text-muted-foreground hover:text-foreground"
            )}
          >
            <GitBranch className="w-4 h-4 inline mr-2" />
            What-If Analysis
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedSeriesId ? (
          <div className="text-center text-muted-foreground py-12">
            <HelpCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Select a series to start working on your plot structure</p>
          </div>
        ) : activeTab === 'beats' ? (
          <div className="space-y-6">
            {/* Generate Beat Sheet */}
            <div className="bg-card border border-border rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Wand2 className="w-5 h-5 text-purple-400" />
                Generate Beat Sheet with AI
              </h2>
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label className="block text-sm text-muted-foreground mb-2">Template</label>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => setSelectedTemplate(e.target.value)}
                    className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  >
                    {templates.map(t => (
                      <option key={t.id} value={t.name}>
                        {t.name} ({t.beat_count} beats)
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleGenerateBeatSheet}
                  disabled={isGenerating}
                  className="px-6 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-medium disabled:opacity-50 flex items-center gap-2"
                >
                  {isGenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  Generate
                </button>
              </div>
            </div>

            {/* Beat List */}
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">Story Beats ({beats.length})</h2>
              {beats.length === 0 ? (
                <div className="text-center text-muted-foreground py-8 border border-dashed border-border rounded-lg">
                  <p>No beats yet. Generate a beat sheet or add beats manually.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {beats.map((beat, index) => (
                    <motion.div
                      key={beat.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="bg-card border border-border rounded-lg overflow-hidden"
                    >
                      <div 
                        className="p-4 flex items-center gap-4 cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => toggleBeatExpanded(beat.id)}
                      >
                        <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 font-bold">
                          {beat.order_index + 1}
                        </div>
                        <div className="flex-1">
                          <h3 className="font-medium">{beat.beat_name}</h3>
                          {beat.beat_description && (
                            <p className="text-sm text-muted-foreground line-clamp-1">{beat.beat_description}</p>
                          )}
                        </div>
                        <select
                          value={beat.status}
                          onChange={(e) => {
                            e.stopPropagation()
                            handleUpdateBeatStatus(beat.id, e.target.value)
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className={cn(
                            "px-3 py-1 rounded-full text-xs font-medium border",
                            getStatusColor(beat.status)
                          )}
                        >
                          <option value="planned">Planned</option>
                          <option value="drafted">Drafted</option>
                          <option value="completed">Completed</option>
                        </select>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeleteBeat(beat.id)
                          }}
                          className="p-2 hover:bg-red-500/20 rounded-lg text-muted-foreground hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        {expandedBeats.has(beat.id) ? (
                          <ChevronDown className="w-5 h-5 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="w-5 h-5 text-muted-foreground" />
                        )}
                      </div>
                      
                      <AnimatePresence>
                        {expandedBeats.has(beat.id) && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="border-t border-border bg-muted/30"
                          >
                            <div className="p-4 space-y-3">
                              {beat.beat_description && (
                                <div>
                                  <label className="text-xs text-muted-foreground uppercase">Description</label>
                                  <p className="mt-1">{beat.beat_description}</p>
                                </div>
                              )}
                              {beat.ai_suggestions && (
                                <div>
                                  <label className="text-xs text-muted-foreground uppercase flex items-center gap-1">
                                    <Sparkles className="w-3 h-3" /> AI Suggestions
                                  </label>
                                  <p className="mt-1 text-sm text-purple-300">{beat.ai_suggestions}</p>
                                </div>
                              )}
                              {beat.chapter_title && (
                                <div>
                                  <label className="text-xs text-muted-foreground uppercase">Linked Chapter</label>
                                  <p className="mt-1">{beat.chapter_title}</p>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Create What-If */}
            <div className="bg-card border border-border rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-yellow-400" />
                Create What-If Scenario
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-2">Scenario Title</label>
                  <input
                    type="text"
                    value={whatIfTitle}
                    onChange={(e) => setWhatIfTitle(e.target.value)}
                    placeholder="e.g., What if the villain won?"
                    className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm text-muted-foreground mb-2">What If...?</label>
                  <textarea
                    value={whatIfPremise}
                    onChange={(e) => setWhatIfPremise(e.target.value)}
                    placeholder="Describe the alternative scenario in detail..."
                    rows={3}
                    className="w-full bg-muted border border-border rounded-lg px-4 py-2 resize-none"
                  />
                </div>
                <button
                  onClick={handleCreateWhatIf}
                  disabled={isCreatingWhatIf || !whatIfTitle || !whatIfPremise}
                  className="px-6 py-2 bg-yellow-500 hover:bg-yellow-600 text-black rounded-lg font-medium disabled:opacity-50 flex items-center gap-2"
                >
                  {isCreatingWhatIf ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <GitBranch className="w-4 h-4" />
                  )}
                  Analyze Scenario
                </button>
              </div>
            </div>

            {/* Variations List */}
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">What-If Scenarios ({variations.length})</h2>
              {variations.length === 0 ? (
                <div className="text-center text-muted-foreground py-8 border border-dashed border-border rounded-lg">
                  <p>No what-if scenarios yet. Create one above!</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {variations.map((variation) => (
                    <motion.div
                      key={variation.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-card border border-border rounded-xl p-6"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h3 className="text-lg font-semibold">{variation.variation_title}</h3>
                          <p className="text-muted-foreground">{variation.what_if_premise}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteVariation(variation.id)}
                          className="p-2 hover:bg-red-500/20 rounded-lg text-muted-foreground hover:text-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      
                      {variation.ai_analysis && (
                        <div className="mb-4 p-4 bg-muted/50 rounded-lg">
                          <h4 className="text-sm font-medium text-purple-400 mb-2 flex items-center gap-1">
                            <Sparkles className="w-4 h-4" /> AI Analysis
                          </h4>
                          <p className="text-sm">{variation.ai_analysis}</p>
                        </div>
                      )}
                      
                      {variation.consequences && variation.consequences.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium mb-2">Consequences</h4>
                          <div className="space-y-2">
                            {variation.consequences.map((c, i) => (
                              <div key={i} className="flex items-start gap-2 text-sm">
                                <AlertCircle className={cn("w-4 h-4 mt-0.5", getSeverityColor(c.severity))} />
                                <div>
                                  <span className="text-xs uppercase text-muted-foreground">{c.type}</span>
                                  <p>{c.description}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}





