import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BookOpen,
  Library,
  Sparkles,
  AlertTriangle,
  CheckCircle,
  Plus,
  ChevronRight,
  Search,
  Loader2,
  Lightbulb,
  Shield,
  Users,
  Clock
} from 'lucide-react'
import { storyApi, type Series, type Book, type Foreshadowing, type WorldRule } from '@/lib/api'
import { cn } from '@/lib/utils'

type Tab = 'series' | 'foreshadowing' | 'rules' | 'analysis'

export function StoryPage() {
  const [activeTab, setActiveTab] = useState<Tab>('series')
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeries, setSelectedSeries] = useState<(Series & { books: Book[] }) | null>(null)
  const [foreshadowing, setForeshadowing] = useState<Foreshadowing[]>([])
  const [worldRules, setWorldRules] = useState<WorldRule[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Forms
  const [showSeriesForm, setShowSeriesForm] = useState(false)
  const [showBookForm, setShowBookForm] = useState(false)
  const [showSeedForm, setShowSeedForm] = useState(false)
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [showAnalysis, setShowAnalysis] = useState(false)

  // Analysis
  const [analysisType, setAnalysisType] = useState<'consistency' | 'knowledge' | 'foreshadowing'>('consistency')
  const [analysisContent, setAnalysisContent] = useState('')
  const [analysisCharacter, setAnalysisCharacter] = useState('')
  const [analysisQuestion, setAnalysisQuestion] = useState('')
  const [analysisChapter, setAnalysisChapter] = useState(1)
  const [analysisResult, setAnalysisResult] = useState<Record<string, unknown> | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  useEffect(() => {
    loadSeries()
  }, [])

  useEffect(() => {
    if (selectedSeries) {
      loadForeshadowing(selectedSeries.id)
      loadWorldRules(selectedSeries.id)
    }
  }, [selectedSeries])

  const loadSeries = async () => {
    try {
      setIsLoading(true)
      const seriesData = await storyApi.listSeries()
      setSeries(seriesData)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setIsLoading(false)
    }
  }

  const loadSeriesDetails = async (id: number) => {
    try {
      const details = await storyApi.getSeries(id)
      setSelectedSeries(details)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const loadForeshadowing = async (seriesId: number) => {
    try {
      const seeds = await storyApi.listForeshadowing(seriesId)
      setForeshadowing(seeds)
    } catch (e) {
      console.error('Failed to load foreshadowing:', e)
    }
  }

  const loadWorldRules = async (seriesId: number) => {
    try {
      const rules = await storyApi.listWorldRules(seriesId)
      setWorldRules(rules)
    } catch (e) {
      console.error('Failed to load world rules:', e)
    }
  }

  const runAnalysis = async () => {
    if (!selectedSeries) return
    
    setIsAnalyzing(true)
    setAnalysisResult(null)
    
    try {
      let result
      switch (analysisType) {
        case 'consistency':
          result = await storyApi.checkConsistency({
            content: analysisContent,
            series_id: selectedSeries.id
          })
          break
        case 'knowledge':
          result = await storyApi.queryKnowledge({
            character_name: analysisCharacter,
            question: analysisQuestion,
            as_of_chapter: analysisChapter,
            series_id: selectedSeries.id
          })
          break
        case 'foreshadowing':
          result = await storyApi.analyzeForeshadowing({
            chapter_content: analysisContent,
            series_id: selectedSeries.id,
            current_book: 1,
            current_chapter: analysisChapter
          })
          break
      }
      setAnalysisResult(result)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const tabs = [
    { id: 'series' as Tab, label: 'Series & Books', icon: Library },
    { id: 'foreshadowing' as Tab, label: 'Foreshadowing', icon: Lightbulb },
    { id: 'rules' as Tab, label: 'World Rules', icon: Shield },
    { id: 'analysis' as Tab, label: 'AI Analysis', icon: Sparkles }
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-bold text-foreground">Story Management</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage your series, track foreshadowing, and run AI-powered analysis
            </p>
          </div>
          {selectedSeries && (
            <div className="px-4 py-2 rounded-lg bg-primary/10 border border-primary/20">
              <span className="text-sm text-muted-foreground">Active Series:</span>
              <span className="ml-2 font-medium text-primary">{selectedSeries.title}</span>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                activeTab === tab.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-card hover:bg-accent/20 text-muted-foreground'
              )}
            >
              <tab.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Error display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mx-6 mt-4 p-4 rounded-lg bg-destructive/10 border border-destructive/30"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-destructive" />
                <p className="text-sm text-destructive">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="text-xs hover:underline">
                Dismiss
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* Series & Books Tab */}
        {activeTab === 'series' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Series List */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Your Series</h2>
                <button
                  onClick={() => setShowSeriesForm(true)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                >
                  <Plus className="w-4 h-4" />
                  New Series
                </button>
              </div>

              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : series.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Library className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No series yet. Create your first one!</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {series.map(s => (
                    <button
                      key={s.id}
                      onClick={() => loadSeriesDetails(s.id)}
                      className={cn(
                        'w-full p-4 rounded-lg border text-left transition-colors',
                        selectedSeries?.id === s.id
                          ? 'border-primary bg-primary/5'
                          : 'border-border/50 bg-card hover:bg-accent/10'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-foreground">{s.title}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {s.book_count || 0} / {s.total_planned_books} books
                          </p>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground" />
                      </div>
                      {s.themes && s.themes.length > 0 && (
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {s.themes.slice(0, 3).map((theme, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded-full bg-accent/20 text-xs text-accent"
                            >
                              {theme}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Series Details */}
            <div className="space-y-4">
              {selectedSeries ? (
                <>
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Books in {selectedSeries.title}</h2>
                    <button
                      onClick={() => setShowBookForm(true)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-sm"
                    >
                      <Plus className="w-4 h-4" />
                      Add Book
                    </button>
                  </div>

                  {selectedSeries.premise && (
                    <div className="p-4 rounded-lg bg-card/50 border border-border/30">
                      <h4 className="text-sm font-medium text-muted-foreground mb-1">Premise</h4>
                      <p className="text-sm">{selectedSeries.premise}</p>
                    </div>
                  )}

                  <div className="space-y-2">
                    {selectedSeries.books?.map(book => (
                      <div
                        key={book.id}
                        className="p-4 rounded-lg bg-card border border-border/50"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <BookOpen className="w-4 h-4 text-primary" />
                              <span className="text-sm text-muted-foreground">
                                Book {book.book_number}
                              </span>
                            </div>
                            <h3 className="font-medium mt-1">{book.title}</h3>
                            {book.theme && (
                              <p className="text-sm text-muted-foreground mt-1">{book.theme}</p>
                            )}
                          </div>
                          <div className="text-right">
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-xs',
                              book.status === 'published' ? 'bg-green-500/20 text-green-500' :
                              book.status === 'editing' ? 'bg-yellow-500/20 text-yellow-500' :
                              book.status === 'drafting' ? 'bg-blue-500/20 text-blue-500' :
                              'bg-muted text-muted-foreground'
                            )}>
                              {book.status}
                            </span>
                            <p className="text-xs text-muted-foreground mt-1">
                              {book.chapter_count || 0} chapters
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>Select a series to view details</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Foreshadowing Tab */}
        {activeTab === 'foreshadowing' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Foreshadowing Seeds</h2>
              <button
                onClick={() => setShowSeedForm(true)}
                disabled={!selectedSeries}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Plant Seed
              </button>
            </div>

            {!selectedSeries ? (
              <div className="text-center py-8 text-muted-foreground">
                Select a series first to manage foreshadowing
              </div>
            ) : foreshadowing.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Lightbulb className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No foreshadowing seeds planted yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {foreshadowing.map(seed => (
                  <motion.div
                    key={seed.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      'p-4 rounded-lg border',
                      seed.status === 'paid_off' ? 'bg-green-500/5 border-green-500/30' :
                      seed.status === 'reinforced' ? 'bg-yellow-500/5 border-yellow-500/30' :
                      'bg-card border-border/50'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <Lightbulb className={cn(
                          'w-4 h-4',
                          seed.status === 'paid_off' ? 'text-green-500' :
                          seed.status === 'reinforced' ? 'text-yellow-500' :
                          'text-primary'
                        )} />
                        <h3 className="font-medium">{seed.title}</h3>
                      </div>
                      <span className={cn(
                        'px-2 py-0.5 rounded-full text-xs',
                        seed.status === 'paid_off' ? 'bg-green-500/20 text-green-500' :
                        seed.status === 'reinforced' ? 'bg-yellow-500/20 text-yellow-500' :
                        'bg-primary/20 text-primary'
                      )}>
                        {seed.status}
                      </span>
                    </div>
                    
                    <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                      "{seed.planted_text}"
                    </p>
                    
                    <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                      <span>Book {seed.planted_book}, Ch. {seed.planted_chapter}</span>
                      <span>Subtlety: {'⭐'.repeat(seed.subtlety)}</span>
                    </div>
                    
                    {seed.intended_payoff && (
                      <div className="mt-2 p-2 rounded bg-background/50">
                        <span className="text-xs font-medium">Intended payoff:</span>
                        <p className="text-xs text-muted-foreground">{seed.intended_payoff}</p>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* World Rules Tab */}
        {activeTab === 'rules' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">World Rules</h2>
              <button
                onClick={() => setShowRuleForm(true)}
                disabled={!selectedSeries}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Add Rule
              </button>
            </div>

            {!selectedSeries ? (
              <div className="text-center py-8 text-muted-foreground">
                Select a series first to manage world rules
              </div>
            ) : worldRules.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Shield className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No world rules defined yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                    {worldRules.map(rule => (
                      <div
                        key={rule.id}
                        className="p-4 rounded-lg bg-card border border-border/50"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded bg-accent/20 text-xs text-accent">
                                {rule.rule_category}
                              </span>
                              {rule.is_hard_rule && (
                                <span className="px-2 py-0.5 rounded bg-red-500/20 text-xs text-red-500">
                                  HARD RULE
                                </span>
                              )}
                            </div>
                            <h3 className="font-medium mt-2">{rule.rule_name}</h3>
                            <p className="text-sm text-muted-foreground mt-1">{rule.rule_description}</p>
                          </div>
                        </div>
                    {rule.exceptions && rule.exceptions.length > 0 && (
                      <div className="mt-2">
                        <span className="text-xs text-muted-foreground">Exceptions:</span>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {rule.exceptions.map((ex, i) => (
                            <span key={i} className="px-2 py-0.5 rounded bg-muted text-xs">
                              {ex}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* AI Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="max-w-4xl space-y-6">
            <div>
              <h2 className="text-lg font-semibold">AI-Powered Analysis</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Use LLM to check consistency, query character knowledge, or analyze foreshadowing
              </p>
            </div>

            {!selectedSeries ? (
              <div className="text-center py-8 text-muted-foreground">
                Select a series first to run analysis
              </div>
            ) : (
              <>
                {/* Analysis Type Selection */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setAnalysisType('consistency')}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                      analysisType === 'consistency'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-card border border-border/50'
                    )}
                  >
                    <AlertTriangle className="w-4 h-4" />
                    Consistency Check
                  </button>
                  <button
                    onClick={() => setAnalysisType('knowledge')}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                      analysisType === 'knowledge'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-card border border-border/50'
                    )}
                  >
                    <Users className="w-4 h-4" />
                    Character Knowledge
                  </button>
                  <button
                    onClick={() => setAnalysisType('foreshadowing')}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                      analysisType === 'foreshadowing'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-card border border-border/50'
                    )}
                  >
                    <Lightbulb className="w-4 h-4" />
                    Foreshadowing Analysis
                  </button>
                </div>

                {/* Input Form */}
                <div className="p-4 rounded-lg bg-card border border-border/50 space-y-4">
                  {analysisType === 'knowledge' ? (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1">Character Name</label>
                        <input
                          type="text"
                          value={analysisCharacter}
                          onChange={(e) => setAnalysisCharacter(e.target.value)}
                          placeholder="e.g., Harry Potter"
                          className="w-full px-3 py-2 rounded-lg bg-background border border-border"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Question</label>
                        <input
                          type="text"
                          value={analysisQuestion}
                          onChange={(e) => setAnalysisQuestion(e.target.value)}
                          placeholder="e.g., What does Harry know about the prophecy?"
                          className="w-full px-3 py-2 rounded-lg bg-background border border-border"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">As of Chapter</label>
                        <input
                          type="number"
                          value={analysisChapter}
                          onChange={(e) => setAnalysisChapter(parseInt(e.target.value) || 1)}
                          min={1}
                          className="w-32 px-3 py-2 rounded-lg bg-background border border-border"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {analysisType === 'consistency' ? 'Content to Check' : 'Chapter Content'}
                        </label>
                        <textarea
                          value={analysisContent}
                          onChange={(e) => setAnalysisContent(e.target.value)}
                          placeholder="Paste your content here..."
                          rows={6}
                          className="w-full px-3 py-2 rounded-lg bg-background border border-border resize-none"
                        />
                      </div>
                      {analysisType === 'foreshadowing' && (
                        <div>
                          <label className="block text-sm font-medium mb-1">Current Chapter</label>
                          <input
                            type="number"
                            value={analysisChapter}
                            onChange={(e) => setAnalysisChapter(parseInt(e.target.value) || 1)}
                            min={1}
                            className="w-32 px-3 py-2 rounded-lg bg-background border border-border"
                          />
                        </div>
                      )}
                    </>
                  )}

                  <button
                    onClick={runAnalysis}
                    disabled={isAnalyzing}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground disabled:opacity-50"
                  >
                    {isAnalyzing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Search className="w-4 h-4" />
                    )}
                    Run Analysis
                  </button>
                </div>

                {/* Results */}
                {analysisResult && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 rounded-lg bg-card border border-border/50"
                  >
                    <h3 className="font-medium flex items-center gap-2 mb-3">
                      <Sparkles className="w-4 h-4 text-primary" />
                      Analysis Results
                    </h3>
                    <pre className="text-sm bg-background p-4 rounded-lg overflow-auto max-h-96">
                      {JSON.stringify(analysisResult, null, 2)}
                    </pre>
                  </motion.div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Series Form Modal */}
      <AnimatePresence>
        {showSeriesForm && (
          <SeriesFormModal
            onClose={() => setShowSeriesForm(false)}
            onSuccess={() => {
              setShowSeriesForm(false)
              loadSeries()
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// Simple Series Form Modal
function SeriesFormModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [title, setTitle] = useState('')
  const [premise, setPremise] = useState('')
  const [themes, setThemes] = useState('')
  const [totalBooks, setTotalBooks] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      await storyApi.createSeries({
        title,
        premise,
        themes: themes.split(',').map(t => t.trim()).filter(Boolean),
        total_planned_books: totalBooks
      })
      onSuccess()
    } catch (e) {
      console.error('Failed to create series:', e)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-card p-6 rounded-xl shadow-xl max-w-md w-full mx-4"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-xl font-semibold mb-4">Create New Series</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-lg bg-background border border-border"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Premise</label>
            <textarea
              value={premise}
              onChange={e => setPremise(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 rounded-lg bg-background border border-border resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Themes (comma separated)</label>
            <input
              type="text"
              value={themes}
              onChange={e => setThemes(e.target.value)}
              placeholder="e.g., Love, Betrayal, Redemption"
              className="w-full px-3 py-2 rounded-lg bg-background border border-border"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Planned Books</label>
            <input
              type="number"
              value={totalBooks}
              onChange={e => setTotalBooks(parseInt(e.target.value) || 1)}
              min={1}
              className="w-32 px-3 py-2 rounded-lg bg-background border border-border"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-border"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground disabled:opacity-50"
            >
              {isSubmitting ? 'Creating...' : 'Create Series'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}

