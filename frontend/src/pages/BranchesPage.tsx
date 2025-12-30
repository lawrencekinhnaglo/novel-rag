import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  GitBranch, Plus, Trash2, ChevronRight, Edit2, Save, X,
  Loader2, BookOpen, FileText, ArrowRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { branchesApi, storyApi, type StoryBranch, type BranchChapter, type Series } from '@/lib/api'

export function BranchesPage() {
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [branches, setBranches] = useState<StoryBranch[]>([])
  const [selectedBranch, setSelectedBranch] = useState<StoryBranch | null>(null)
  const [branchChapters, setBranchChapters] = useState<BranchChapter[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreatingBranch, setIsCreatingBranch] = useState(false)
  const [isAddingChapter, setIsAddingChapter] = useState(false)
  const [editingChapterId, setEditingChapterId] = useState<number | null>(null)
  
  // Form state
  const [branchForm, setBranchForm] = useState({
    branch_name: '',
    branch_description: '',
    divergence_description: ''
  })
  
  const [chapterForm, setChapterForm] = useState({
    title: '',
    content: '',
    chapter_number: 1
  })

  useEffect(() => {
    loadSeries()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadBranches()
    }
  }, [selectedSeriesId])

  useEffect(() => {
    if (selectedBranch) {
      loadBranchChapters()
    }
  }, [selectedBranch])

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

  const loadBranches = async () => {
    if (!selectedSeriesId) return
    try {
      const data = await branchesApi.list(selectedSeriesId)
      setBranches(data)
    } catch (error) {
      console.error('Failed to load branches:', error)
    }
  }

  const loadBranchChapters = async () => {
    if (!selectedBranch) return
    try {
      const data = await branchesApi.getChapters(selectedBranch.id)
      setBranchChapters(data)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const handleCreateBranch = async () => {
    if (!selectedSeriesId || !branchForm.branch_name) return
    try {
      await branchesApi.create({
        series_id: selectedSeriesId,
        ...branchForm
      })
      await loadBranches()
      setIsCreatingBranch(false)
      setBranchForm({ branch_name: '', branch_description: '', divergence_description: '' })
    } catch (error) {
      console.error('Failed to create branch:', error)
    }
  }

  const handleDeleteBranch = async (branchId: number) => {
    try {
      await branchesApi.delete(branchId)
      setBranches(branches.filter(b => b.id !== branchId))
      if (selectedBranch?.id === branchId) {
        setSelectedBranch(null)
        setBranchChapters([])
      }
    } catch (error) {
      console.error('Failed to delete branch:', error)
    }
  }

  const handleCreateChapter = async () => {
    if (!selectedBranch || !chapterForm.title || !chapterForm.content) return
    try {
      await branchesApi.createChapter({
        branch_id: selectedBranch.id,
        ...chapterForm
      })
      await loadBranchChapters()
      await loadBranches()
      setIsAddingChapter(false)
      setChapterForm({ title: '', content: '', chapter_number: branchChapters.length + 1 })
    } catch (error) {
      console.error('Failed to create chapter:', error)
    }
  }

  const handleUpdateChapter = async (chapterId: number) => {
    try {
      await branchesApi.updateChapter(chapterId, chapterForm)
      await loadBranchChapters()
      setEditingChapterId(null)
    } catch (error) {
      console.error('Failed to update chapter:', error)
    }
  }

  const handleDeleteChapter = async (chapterId: number) => {
    try {
      await branchesApi.deleteChapter(chapterId)
      setBranchChapters(branchChapters.filter(c => c.id !== chapterId))
      await loadBranches()
    } catch (error) {
      console.error('Failed to delete chapter:', error)
    }
  }

  const startEditChapter = (chapter: BranchChapter) => {
    setEditingChapterId(chapter.id)
    setChapterForm({
      title: chapter.title,
      content: chapter.content,
      chapter_number: chapter.chapter_number || 1
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="h-full flex">
      {/* Sidebar - Branch List */}
      <div className="w-80 border-r border-border flex flex-col bg-gradient-to-b from-orange-900/10 to-background">
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2 mb-4">
            <GitBranch className="w-5 h-5 text-orange-400" />
            <h2 className="font-semibold">Story Branches</h2>
          </div>
          
          <select
            value={selectedSeriesId || ''}
            onChange={(e) => {
              setSelectedSeriesId(Number(e.target.value))
              setSelectedBranch(null)
              setBranchChapters([])
            }}
            className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm mb-3"
          >
            <option value="">Select series...</option>
            {series.map(s => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
          
          <button
            onClick={() => setIsCreatingBranch(true)}
            disabled={!selectedSeriesId}
            className="w-full px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Branch
          </button>
        </div>

        {/* Branch List */}
        <div className="flex-1 overflow-auto p-2">
          {branches.length === 0 ? (
            <div className="text-center text-muted-foreground py-8 text-sm">
              <GitBranch className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No branches yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {branches.map(branch => (
                <div
                  key={branch.id}
                  onClick={() => setSelectedBranch(branch)}
                  className={cn(
                    "p-3 rounded-lg cursor-pointer transition-colors",
                    selectedBranch?.id === branch.id 
                      ? "bg-orange-500/20 border border-orange-500/30" 
                      : "hover:bg-muted border border-transparent"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{branch.branch_name}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteBranch(branch.id) }}
                      className="p-1 hover:bg-red-500/20 rounded text-muted-foreground hover:text-red-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                    {branch.divergence_description || 'No description'}
                  </p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                    <FileText className="w-3 h-3" />
                    <span>{branch.chapter_count} chapters</span>
                    {branch.is_merged && (
                      <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">merged</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-border">
          {selectedBranch ? (
            <div>
              <h1 className="text-2xl font-display font-bold">{selectedBranch.branch_name}</h1>
              {selectedBranch.divergence_description && (
                <p className="text-muted-foreground mt-1">{selectedBranch.divergence_description}</p>
              )}
              {selectedBranch.branch_point_chapter_title && (
                <p className="text-sm text-orange-400 mt-2 flex items-center gap-1">
                  <ArrowRight className="w-4 h-4" />
                  Branches from: {selectedBranch.branch_point_chapter_title}
                </p>
              )}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              <GitBranch className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Select a branch or create a new one</p>
            </div>
          )}
        </div>

        {/* Chapters */}
        {selectedBranch && (
          <div className="flex-1 overflow-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Branch Chapters</h2>
              <button
                onClick={() => {
                  setIsAddingChapter(true)
                  setChapterForm({ ...chapterForm, chapter_number: branchChapters.length + 1 })
                }}
                className="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm flex items-center gap-1"
              >
                <Plus className="w-4 h-4" />
                Add Chapter
              </button>
            </div>

            {/* Add Chapter Form */}
            <AnimatePresence>
              {isAddingChapter && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-4 bg-card border border-border rounded-xl p-4"
                >
                  <h3 className="font-medium mb-3">New Chapter</h3>
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <input
                        type="text"
                        value={chapterForm.title}
                        onChange={(e) => setChapterForm({ ...chapterForm, title: e.target.value })}
                        placeholder="Chapter title"
                        className="flex-1 bg-muted border border-border rounded-lg px-3 py-2"
                      />
                      <input
                        type="number"
                        value={chapterForm.chapter_number}
                        onChange={(e) => setChapterForm({ ...chapterForm, chapter_number: Number(e.target.value) })}
                        className="w-20 bg-muted border border-border rounded-lg px-3 py-2"
                        min={1}
                      />
                    </div>
                    <textarea
                      value={chapterForm.content}
                      onChange={(e) => setChapterForm({ ...chapterForm, content: e.target.value })}
                      placeholder="Write your chapter content..."
                      className="w-full bg-muted border border-border rounded-lg px-3 py-2 resize-none"
                      rows={8}
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setIsAddingChapter(false)}
                        className="px-3 py-1.5 border border-border rounded-lg text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCreateChapter}
                        disabled={!chapterForm.title || !chapterForm.content}
                        className="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-sm disabled:opacity-50"
                      >
                        Create
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Chapter List */}
            {branchChapters.length === 0 ? (
              <div className="text-center text-muted-foreground py-12 border border-dashed border-border rounded-lg">
                <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No chapters in this branch yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {branchChapters.map((chapter, index) => (
                  <motion.div
                    key={chapter.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="bg-card border border-border rounded-xl overflow-hidden"
                  >
                    {editingChapterId === chapter.id ? (
                      <div className="p-4 space-y-3">
                        <div className="flex gap-3">
                          <input
                            type="text"
                            value={chapterForm.title}
                            onChange={(e) => setChapterForm({ ...chapterForm, title: e.target.value })}
                            className="flex-1 bg-muted border border-border rounded-lg px-3 py-2"
                          />
                          <input
                            type="number"
                            value={chapterForm.chapter_number}
                            onChange={(e) => setChapterForm({ ...chapterForm, chapter_number: Number(e.target.value) })}
                            className="w-20 bg-muted border border-border rounded-lg px-3 py-2"
                          />
                        </div>
                        <textarea
                          value={chapterForm.content}
                          onChange={(e) => setChapterForm({ ...chapterForm, content: e.target.value })}
                          className="w-full bg-muted border border-border rounded-lg px-3 py-2 resize-none"
                          rows={10}
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => setEditingChapterId(null)}
                            className="px-3 py-1.5 border border-border rounded-lg text-sm flex items-center gap-1"
                          >
                            <X className="w-3 h-3" /> Cancel
                          </button>
                          <button
                            onClick={() => handleUpdateChapter(chapter.id)}
                            className="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-sm flex items-center gap-1"
                          >
                            <Save className="w-3 h-3" /> Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="p-4 flex items-center justify-between border-b border-border bg-muted/30">
                          <div className="flex items-center gap-3">
                            <span className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center text-orange-400 font-bold text-sm">
                              {chapter.chapter_number || '?'}
                            </span>
                            <div>
                              <h3 className="font-medium">{chapter.title}</h3>
                              <span className="text-xs text-muted-foreground">{chapter.word_count} words</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => startEditChapter(chapter)}
                              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteChapter(chapter.id)}
                              className="p-1.5 hover:bg-red-500/20 rounded-lg text-muted-foreground hover:text-red-400"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                        <div className="p-4 max-h-60 overflow-auto">
                          <p className="text-sm whitespace-pre-wrap">{chapter.content}</p>
                        </div>
                      </>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Branch Modal */}
      <AnimatePresence>
        {isCreatingBranch && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setIsCreatingBranch(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-card border border-border rounded-xl p-6 w-full max-w-md"
              onClick={e => e.stopPropagation()}
            >
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-orange-400" />
                Create New Branch
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Branch Name *</label>
                  <input
                    type="text"
                    value={branchForm.branch_name}
                    onChange={(e) => setBranchForm({ ...branchForm, branch_name: e.target.value })}
                    className="w-full bg-muted border border-border rounded-lg px-3 py-2"
                    placeholder="e.g., Alternative Ending"
                  />
                </div>
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Description</label>
                  <input
                    type="text"
                    value={branchForm.branch_description}
                    onChange={(e) => setBranchForm({ ...branchForm, branch_description: e.target.value })}
                    className="w-full bg-muted border border-border rounded-lg px-3 py-2"
                    placeholder="Short description..."
                  />
                </div>
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">What's Different?</label>
                  <textarea
                    value={branchForm.divergence_description}
                    onChange={(e) => setBranchForm({ ...branchForm, divergence_description: e.target.value })}
                    className="w-full bg-muted border border-border rounded-lg px-3 py-2 resize-none"
                    rows={3}
                    placeholder="How does this branch diverge from the main story?"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setIsCreatingBranch(false)}
                    className="px-4 py-2 border border-border rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateBranch}
                    disabled={!branchForm.branch_name}
                    className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg disabled:opacity-50"
                  >
                    Create Branch
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}


