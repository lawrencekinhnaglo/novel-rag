import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, BookOpen, Edit2, Trash2, Save, X, FileText, 
  Library, Sparkles, CheckCircle, Loader2, AlertCircle
} from 'lucide-react'
import { chaptersApi, ideasApi, storyApi, type Chapter, type Idea, type Series, type Book } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export function ChaptersPage() {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [ideas, setIdeas] = useState<Idea[]>([])
  const [activeTab, setActiveTab] = useState<'chapters' | 'ideas'>('chapters')
  const [isEditing, setIsEditing] = useState<number | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [formData, setFormData] = useState({ 
    title: '', 
    content: '', 
    chapter_number: '',
    book_id: '' 
  })
  const [loading, setLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  
  // Series/Book selection
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [books, setBooks] = useState<Book[]>([])
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    loadSeriesList()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadSeriesDetails(selectedSeriesId)
      loadPendingCount(selectedSeriesId)
    }
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

  const loadSeriesDetails = async (seriesId: number) => {
    try {
      const data = await storyApi.getSeries(seriesId)
      setBooks(data.books || [])
    } catch (error) {
      console.error('Failed to load series details:', error)
    }
  }

  const loadPendingCount = async (seriesId: number) => {
    try {
      const res = await fetch(`${API_BASE}/verification/stats/${seriesId}`)
      const data = await res.json()
      setPendingCount(data.total_pending || 0)
    } catch (error) {
      console.error('Failed to load pending count:', error)
    }
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const [chaptersData, ideasData] = await Promise.all([
        chaptersApi.list(),
        ideasApi.list()
      ])
      // Filter chapters by selected book if any
      setChapters(chaptersData)
      setIdeas(ideasData)
    } catch (error) {
      console.error('Failed to load data:', error)
    }
    setLoading(false)
  }

  const handleCreate = async () => {
    setIsSaving(true)
    setAnalysisResult(null)
    try {
      if (activeTab === 'chapters') {
        const result = await chaptersApi.create({
          title: formData.title,
          content: formData.content,
          chapter_number: formData.chapter_number ? parseInt(formData.chapter_number) : undefined,
          book_id: formData.book_id ? parseInt(formData.book_id) : undefined,
          series_id: selectedSeriesId || undefined
        })
        
        // Show analysis result if available
        if (result.analysis) {
          setAnalysisResult(result.analysis)
        }
        
        // Reload pending count
        if (selectedSeriesId) {
          loadPendingCount(selectedSeriesId)
        }
      } else {
        await ideasApi.create({
          title: formData.title,
          content: formData.content
        })
      }
      setIsCreating(false)
      setFormData({ title: '', content: '', chapter_number: '', book_id: '' })
      loadData()
    } catch (error) {
      console.error('Failed to create:', error)
    }
    setIsSaving(false)
  }

  const handleUpdate = async (id: number) => {
    setIsSaving(true)
    setAnalysisResult(null)
    try {
      const result = await chaptersApi.update(id, {
        title: formData.title,
        content: formData.content,
        chapter_number: formData.chapter_number ? parseInt(formData.chapter_number) : undefined,
        book_id: formData.book_id ? parseInt(formData.book_id) : undefined
      })
      
      // Show analysis result if available
      if (result.analysis) {
        setAnalysisResult(result.analysis)
      }
      
      // Reload pending count
      if (selectedSeriesId) {
        loadPendingCount(selectedSeriesId)
      }
      
      setIsEditing(null)
      setFormData({ title: '', content: '', chapter_number: '', book_id: '' })
      loadData()
    } catch (error) {
      console.error('Failed to update:', error)
    }
    setIsSaving(false)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this?')) return
    try {
      if (activeTab === 'chapters') {
        await chaptersApi.delete(id)
      } else {
        await ideasApi.delete(id)
      }
      loadData()
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const startEdit = (chapter: Chapter) => {
    setIsEditing(chapter.id)
    setFormData({
      title: chapter.title,
      content: chapter.content,
      chapter_number: chapter.chapter_number?.toString() || '',
      book_id: chapter.book_id?.toString() || ''
    })
  }

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header with Series Selector */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-display font-semibold text-foreground">
              Content Library
            </h1>
            <p className="text-muted-foreground">
              Manage your chapters and story ideas
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
          
          {/* Pending Verification Badge */}
          {pendingCount > 0 && (
            <a 
              href="/verification"
              className="flex items-center gap-2 px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm hover:bg-purple-500/30 transition-colors"
            >
              <Sparkles className="w-4 h-4" />
              {pendingCount} pending verification
            </a>
          )}
        </div>
        
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="font-medium">Add {activeTab === 'chapters' ? 'Chapter' : 'Idea'}</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('chapters')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors",
            activeTab === 'chapters'
              ? "bg-primary/20 text-primary"
              : "text-muted-foreground hover:bg-muted"
          )}
        >
          <BookOpen className="w-4 h-4" />
          Chapters ({chapters.length})
        </button>
        <button
          onClick={() => setActiveTab('ideas')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors",
            activeTab === 'ideas'
              ? "bg-accent/20 text-accent"
              : "text-muted-foreground hover:bg-muted"
          )}
        >
          <FileText className="w-4 h-4" />
          Ideas ({ideas.length})
        </button>
      </div>

      {/* Analysis Result Banner */}
      <AnimatePresence>
        {analysisResult && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-4 p-4 rounded-xl bg-purple-500/10 border border-purple-500/30"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <div>
                  <p className="font-medium text-foreground">Auto-Analysis Complete</p>
                  <p className="text-sm text-muted-foreground">
                    Story elements extracted and sent to Verification Hub
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <a 
                  href="/verification" 
                  className="px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm hover:bg-purple-500/30"
                >
                  Review Extractions
                </a>
                <button
                  onClick={() => setAnalysisResult(null)}
                  className="p-1 hover:bg-muted rounded"
                >
                  <X className="w-4 h-4 text-muted-foreground" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create/Edit Form */}
      <AnimatePresence>
        {(isCreating || isEditing !== null) && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-card border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">
                {isEditing !== null ? 'Edit Chapter' : `New ${activeTab === 'chapters' ? 'Chapter' : 'Idea'}`}
              </h3>
              <button
                onClick={() => {
                  setIsCreating(false)
                  setIsEditing(null)
                  setFormData({ title: '', content: '', chapter_number: '', book_id: '' })
                }}
                className="p-1 hover:bg-muted rounded"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="flex gap-4">
                <input
                  type="text"
                  placeholder="Title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                />
                {activeTab === 'chapters' && (
                  <>
                    <input
                      type="number"
                      placeholder="Chapter #"
                      value={formData.chapter_number}
                      onChange={(e) => setFormData({ ...formData, chapter_number: e.target.value })}
                      className="w-32 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    />
                    {books.length > 0 && (
                      <select
                        value={formData.book_id}
                        onChange={(e) => setFormData({ ...formData, book_id: e.target.value })}
                        className="w-48 px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
                      >
                        <option value="">Select Book</option>
                        {books.map(book => (
                          <option key={book.id} value={book.id}>
                            Book {book.book_number}: {book.title}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                )}
              </div>
              <textarea
                placeholder="Content..."
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                rows={8}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
              />
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  <Sparkles className="w-3 h-3" />
                  Saving will auto-extract characters, world rules, and foreshadowing
                </p>
                <button
                  onClick={() => isEditing !== null ? handleUpdate(isEditing) : handleCreate()}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="font-medium">Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      <span className="font-medium">Save & Analyze</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : activeTab === 'chapters' ? (
          <div className="grid gap-4">
            {chapters.map((chapter) => (
              <motion.div
                key={chapter.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-primary/30 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {chapter.chapter_number && (
                        <span className="px-2 py-0.5 rounded bg-primary/20 text-primary text-xs font-medium">
                          Chapter {chapter.chapter_number}
                        </span>
                      )}
                      {chapter.book_id && books.find(b => b.id === chapter.book_id) && (
                        <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                          {books.find(b => b.id === chapter.book_id)?.title}
                        </span>
                      )}
                      <h3 className="font-display font-semibold text-foreground">
                        {chapter.title}
                      </h3>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                      {chapter.content}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{chapter.word_count} words</span>
                      <span>Updated {formatDate(chapter.updated_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => startEdit(chapter)}
                      className="p-2 hover:bg-muted rounded-lg transition-colors"
                    >
                      <Edit2 className="w-4 h-4 text-muted-foreground" />
                    </button>
                    <button
                      onClick={() => handleDelete(chapter.id)}
                      className="p-2 hover:bg-destructive/20 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
            {chapters.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No chapters yet. Create your first chapter!</p>
              </div>
            )}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {ideas.map((idea) => (
              <motion.div
                key={idea.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-accent/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-foreground">{idea.title}</h3>
                  <button
                    onClick={() => handleDelete(idea.id)}
                    className="p-1 hover:bg-destructive/20 rounded transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-destructive" />
                  </button>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                  {idea.content}
                </p>
                {idea.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {idea.tags.map((tag) => (
                      <span key={tag} className="px-2 py-0.5 rounded bg-accent/10 text-accent text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
            {ideas.length === 0 && (
              <div className="col-span-2 text-center py-12 text-muted-foreground">
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No ideas yet. Capture your first idea!</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
