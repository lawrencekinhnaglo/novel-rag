import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Download, FileText, Book, Loader2, Check, 
  BookOpen, Settings, Sparkles, Globe, Users,
  CheckSquare, Square, FileJson, FileCode, Package,
  AlertCircle, ChevronDown, ArrowRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { storyApi, chaptersApi, knowledgeApi, type Series, type Chapter, type Knowledge } from '@/lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type ExportFormat = 'docx' | 'markdown' | 'json'
type ExportType = 'series' | 'chapters' | 'knowledge'

interface ExportOptions {
  format: ExportFormat
  include_metadata: boolean
  include_worldbuilding: boolean
  include_chapters: boolean
  include_characters: boolean
  include_timeline: boolean
  language: string
}

export function ExportPage() {
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [knowledge, setKnowledge] = useState<Knowledge[]>([])
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [exportType, setExportType] = useState<ExportType>('series')
  const [exportOptions, setExportOptions] = useState<ExportOptions>({
    format: 'docx',
    include_metadata: true,
    include_worldbuilding: true,
    include_chapters: true,
    include_characters: true,
    include_timeline: false,
    language: 'zh-TW'
  })
  const [exportComplete, setExportComplete] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    loadSeries()
    loadKnowledge()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadChapters()
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

  const loadChapters = async () => {
    try {
      const data = await chaptersApi.list()
      setChapters(data)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    }
  }

  const loadKnowledge = async () => {
    try {
      const data = await knowledgeApi.list()
      setKnowledge(data)
    } catch (error) {
      console.error('Failed to load knowledge:', error)
    }
  }

  const toggleChapter = (id: number) => {
    const newSelected = new Set(selectedChapterIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedChapterIds(newSelected)
  }

  const selectAll = () => {
    setSelectedChapterIds(new Set(chapters.map(c => c.id)))
  }

  const selectNone = () => {
    setSelectedChapterIds(new Set())
  }

  const handleExport = async () => {
    if (!selectedSeriesId && exportType === 'series') {
      setExportError('Please select a series')
      return
    }

    setIsExporting(true)
    setExportError(null)
    
    try {
      let endpoint = ''
      let body: any = { ...exportOptions }
      
      if (exportType === 'series') {
        endpoint = `${API_BASE}/export/series/${selectedSeriesId}`
      } else if (exportType === 'knowledge') {
        endpoint = `${API_BASE}/export/knowledge${selectedSeriesId ? `?series_id=${selectedSeriesId}` : ''}`
      } else {
        // Client-side chapter export (existing functionality)
        await exportChaptersClientSide()
        return
      }
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      })
      
      if (!response.ok) {
        throw new Error('Export failed')
      }
      
      // Get filename from Content-Disposition header
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = 'export'
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/)
        if (match) {
          filename = match[1]
        }
      }
      
      // Download the file
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      setExportComplete(true)
      setTimeout(() => setExportComplete(false), 3000)
    } catch (error) {
      console.error('Export failed:', error)
      setExportError('Export failed. Please try again.')
    } finally {
      setIsExporting(false)
    }
  }

  const exportChaptersClientSide = async () => {
    const selectedChapters = chapters.filter(c => selectedChapterIds.has(c.id))
    if (selectedChapters.length === 0) {
      setExportError('Please select at least one chapter')
      return
    }
    
    selectedChapters.sort((a, b) => (a.chapter_number || 0) - (b.chapter_number || 0))
    
    let content = ''
    let filename = ''
    let mimeType = ''
    
    const selectedSeriesTitle = series.find(s => s.id === selectedSeriesId)?.title || 'Export'
    
    switch (exportOptions.format) {
      case 'markdown':
        content = generateMarkdown(selectedChapters, selectedSeriesTitle)
        filename = `${selectedSeriesTitle.replace(/\s+/g, '_')}_chapters.md`
        mimeType = 'text/markdown'
        break
      case 'json':
        content = generateJSON(selectedChapters, selectedSeriesTitle)
        filename = `${selectedSeriesTitle.replace(/\s+/g, '_')}_chapters.json`
        mimeType = 'application/json'
        break
      default:
        // For DOCX, use server-side export
        await handleExport()
        return
    }
    
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    setExportComplete(true)
    setTimeout(() => setExportComplete(false), 3000)
  }

  const generateMarkdown = (chapters: Chapter[], title: string): string => {
    let content = ''
    
    if (exportOptions.include_metadata) {
      content += `# ${title}\n\n`
      content += `> Exported on ${new Date().toLocaleDateString()}\n\n`
      content += `---\n\n`
    }
    
    for (const chapter of chapters) {
      content += `## Chapter ${chapter.chapter_number}: ${chapter.title}\n\n`
      content += `${chapter.content}\n\n`
      content += `---\n\n`
    }
    
    return content
  }

  const generateJSON = (chapters: Chapter[], title: string): string => {
    const data = {
      title,
      exported_at: new Date().toISOString(),
      chapter_count: chapters.length,
      total_words: chapters.reduce((sum, c) => sum + (c.word_count || 0), 0),
      chapters: chapters.map(c => ({
        title: c.title,
        chapter_number: c.chapter_number,
        word_count: c.word_count,
        content: c.content
      }))
    }
    return JSON.stringify(data, null, 2)
  }

  const totalWords = chapters
    .filter(c => selectedChapterIds.has(c.id))
    .reduce((sum, c) => sum + (c.word_count || 0), 0)

  const formatIcons: Record<ExportFormat, any> = {
    docx: Package,
    markdown: FileCode,
    json: FileJson
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
      <div className="flex-shrink-0 p-6 border-b border-border bg-gradient-to-r from-pink-900/20 via-purple-900/20 to-rose-900/20">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-pink-500/20 to-purple-500/20">
            <Download className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold">Export Center</h1>
            <p className="text-muted-foreground">Export your story, worldbuilding, and more</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          {/* Export Type Selector */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { type: 'series' as ExportType, label: 'Complete Series', labelZh: '完整系列', icon: Book, desc: 'Export everything' },
              { type: 'chapters' as ExportType, label: 'Selected Chapters', labelZh: '選擇章節', icon: BookOpen, desc: 'Pick specific chapters' },
              { type: 'knowledge' as ExportType, label: 'Knowledge Base', labelZh: '知識庫', icon: Globe, desc: 'Worldbuilding & notes' }
            ].map(({ type, label, labelZh, icon: Icon, desc }) => (
              <button
                key={type}
                onClick={() => setExportType(type)}
                className={cn(
                  "p-4 rounded-xl border-2 text-left transition-all",
                  exportType === type
                    ? "border-pink-500 bg-pink-500/10"
                    : "border-border hover:border-pink-500/50"
                )}
              >
                <Icon className={cn(
                  "w-6 h-6 mb-2",
                  exportType === type ? "text-pink-400" : "text-muted-foreground"
                )} />
                <h3 className="font-semibold">{labelZh}</h3>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Selection */}
            <div className="lg:col-span-2 space-y-6">
              {/* Series Selector */}
              <div className="bg-card border border-border rounded-xl p-4">
                <label className="block text-sm text-muted-foreground mb-2">Select Series / 選擇系列</label>
                <select
                  value={selectedSeriesId || ''}
                  onChange={(e) => {
                    setSelectedSeriesId(Number(e.target.value))
                    setSelectedChapterIds(new Set())
                  }}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                >
                  <option value="">Choose a series...</option>
                  {series.map(s => (
                    <option key={s.id} value={s.id}>{s.title}</option>
                  ))}
                </select>
              </div>

              {/* Chapter Selection - only for chapters type */}
              {exportType === 'chapters' && (
                <div className="bg-card border border-border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold flex items-center gap-2">
                      <BookOpen className="w-5 h-5 text-pink-400" />
                      Select Chapters / 選擇章節
                    </h3>
                    <div className="flex gap-2">
                      <button onClick={selectAll} className="text-sm text-pink-400 hover:underline">
                        All
                      </button>
                      <span className="text-muted-foreground">|</span>
                      <button onClick={selectNone} className="text-sm text-pink-400 hover:underline">
                        None
                      </button>
                    </div>
                  </div>

                  {chapters.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>No chapters available</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-80 overflow-auto">
                      {chapters
                        .sort((a, b) => (a.chapter_number || 0) - (b.chapter_number || 0))
                        .map(chapter => (
                        <label
                          key={chapter.id}
                          className={cn(
                            "flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors",
                            selectedChapterIds.has(chapter.id) 
                              ? "bg-pink-500/20 border border-pink-500/30" 
                              : "hover:bg-muted border border-transparent"
                          )}
                        >
                          {selectedChapterIds.has(chapter.id) ? (
                            <CheckSquare className="w-5 h-5 text-pink-400" />
                          ) : (
                            <Square className="w-5 h-5 text-muted-foreground" />
                          )}
                          <input
                            type="checkbox"
                            checked={selectedChapterIds.has(chapter.id)}
                            onChange={() => toggleChapter(chapter.id)}
                            className="sr-only"
                          />
                          <div className="flex-1">
                            <span className="font-medium">{chapter.title}</span>
                            <div className="text-xs text-muted-foreground">
                              Chapter {chapter.chapter_number} • {chapter.word_count?.toLocaleString()} words
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Series Export Preview */}
              {exportType === 'series' && selectedSeriesId && (
                <div className="bg-card border border-border rounded-xl p-4">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-pink-400" />
                    Export Preview / 導出預覽
                  </h3>
                  
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                      <Book className="w-5 h-5 text-blue-400" />
                      <div>
                        <p className="font-medium">Series Info</p>
                        <p className="text-xs text-muted-foreground">Title, premise, themes</p>
                      </div>
                      <Check className="w-4 h-4 text-green-400 ml-auto" />
                    </div>
                    
                    {exportOptions.include_worldbuilding && (
                      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                        <Globe className="w-5 h-5 text-emerald-400" />
                        <div>
                          <p className="font-medium">Worldbuilding</p>
                          <p className="text-xs text-muted-foreground">{knowledge.filter(k => k.tags?.includes(`series:${selectedSeriesId}`)).length || 'All'} entries</p>
                        </div>
                        <Check className="w-4 h-4 text-green-400 ml-auto" />
                      </div>
                    )}
                    
                    {exportOptions.include_characters && (
                      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                        <Users className="w-5 h-5 text-purple-400" />
                        <div>
                          <p className="font-medium">Characters</p>
                          <p className="text-xs text-muted-foreground">Names, descriptions, backgrounds</p>
                        </div>
                        <Check className="w-4 h-4 text-green-400 ml-auto" />
                      </div>
                    )}
                    
                    {exportOptions.include_chapters && (
                      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                        <BookOpen className="w-5 h-5 text-pink-400" />
                        <div>
                          <p className="font-medium">Chapters</p>
                          <p className="text-xs text-muted-foreground">{chapters.length} chapters</p>
                        </div>
                        <Check className="w-4 h-4 text-green-400 ml-auto" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Knowledge Export Preview */}
              {exportType === 'knowledge' && (
                <div className="bg-card border border-border rounded-xl p-4">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <Globe className="w-5 h-5 text-emerald-400" />
                    Knowledge Base Preview
                  </h3>
                  
                  <div className="text-center py-6">
                    <p className="text-3xl font-bold text-emerald-400">{knowledge.length}</p>
                    <p className="text-muted-foreground">Total entries to export</p>
                  </div>
                  
                  <div className="flex flex-wrap gap-2">
                    {Array.from(new Set(knowledge.map(k => k.source_type || k.category))).slice(0, 8).map(cat => (
                      <span key={cat} className="px-2 py-1 bg-muted rounded text-xs text-muted-foreground">
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right Column - Options & Export */}
            <div className="space-y-6">
              {/* Export Format */}
              <div className="bg-card border border-border rounded-xl p-4">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-pink-400" />
                  Export Format
                </h3>

                <div className="space-y-2">
                  {(['docx', 'markdown', 'json'] as ExportFormat[]).map(format => {
                    const Icon = formatIcons[format]
                    return (
                      <button
                        key={format}
                        onClick={() => setExportOptions(prev => ({ ...prev, format }))}
                        className={cn(
                          "w-full flex items-center gap-3 p-3 rounded-lg transition-colors text-left",
                          exportOptions.format === format 
                            ? "bg-pink-500/20 border-2 border-pink-500" 
                            : "bg-muted border-2 border-transparent hover:border-pink-500/30"
                        )}
                      >
                        <Icon className={cn(
                          "w-5 h-5",
                          exportOptions.format === format ? "text-pink-400" : "text-muted-foreground"
                        )} />
                        <div>
                          <p className="font-medium">
                            {format === 'docx' && 'Word Document (.docx)'}
                            {format === 'markdown' && 'Markdown (.md)'}
                            {format === 'json' && 'JSON Data (.json)'}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {format === 'docx' && 'Formatted for printing/editing'}
                            {format === 'markdown' && 'Plain text with formatting'}
                            {format === 'json' && 'Structured data for backup'}
                          </p>
                        </div>
                      </button>
                    )
                  })}
                </div>

                {/* Advanced Options */}
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 mt-4 text-sm text-muted-foreground hover:text-foreground"
                >
                  <ChevronDown className={cn("w-4 h-4 transition-transform", showAdvanced && "rotate-180")} />
                  Advanced Options
                </button>
                
                <AnimatePresence>
                  {showAdvanced && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="space-y-2 pt-4 border-t border-border mt-4">
                        {exportType === 'series' && (
                          <>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={exportOptions.include_worldbuilding}
                                onChange={(e) => setExportOptions(prev => ({ ...prev, include_worldbuilding: e.target.checked }))}
                                className="w-4 h-4 rounded border-border accent-pink-500"
                              />
                              <span className="text-sm">Include worldbuilding</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={exportOptions.include_chapters}
                                onChange={(e) => setExportOptions(prev => ({ ...prev, include_chapters: e.target.checked }))}
                                className="w-4 h-4 rounded border-border accent-pink-500"
                              />
                              <span className="text-sm">Include chapters</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={exportOptions.include_characters}
                                onChange={(e) => setExportOptions(prev => ({ ...prev, include_characters: e.target.checked }))}
                                className="w-4 h-4 rounded border-border accent-pink-500"
                              />
                              <span className="text-sm">Include characters</span>
                            </label>
                          </>
                        )}
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={exportOptions.include_metadata}
                            onChange={(e) => setExportOptions(prev => ({ ...prev, include_metadata: e.target.checked }))}
                            className="w-4 h-4 rounded border-border accent-pink-500"
                          />
                          <span className="text-sm">Include metadata</span>
                        </label>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Summary & Export Button */}
              <div className="bg-card border border-border rounded-xl p-4">
                <h3 className="font-semibold mb-4">Export Summary</h3>

                <div className="space-y-2 mb-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Type</span>
                    <span className="font-medium capitalize">{exportType}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Format</span>
                    <span className="font-medium uppercase">{exportOptions.format}</span>
                  </div>
                  {exportType === 'chapters' && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Chapters</span>
                        <span className="font-medium">{selectedChapterIds.size}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Words</span>
                        <span className="font-medium">{totalWords.toLocaleString()}</span>
                      </div>
                    </>
                  )}
                </div>

                {/* Error Message */}
                {exportError && (
                  <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-lg mb-4">
                    <AlertCircle className="w-4 h-4 text-destructive" />
                    <span className="text-sm text-destructive">{exportError}</span>
                  </div>
                )}

                <button
                  onClick={handleExport}
                  disabled={isExporting || (!selectedSeriesId && exportType !== 'knowledge')}
                  className={cn(
                    "w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-all",
                    exportComplete 
                      ? "bg-green-500 text-white" 
                      : "bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                  )}
                >
                  {isExporting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Exporting...
                    </>
                  ) : exportComplete ? (
                    <>
                      <Check className="w-5 h-5" />
                      Downloaded!
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      Export Now
                    </>
                  )}
                </button>
              </div>

              {/* Pro Tip */}
              <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-xl p-4">
                <h4 className="text-sm font-medium text-purple-400 mb-2 flex items-center gap-1">
                  <Sparkles className="w-4 h-4" />
                  Pro Tip
                </h4>
                <p className="text-xs text-muted-foreground">
                  Export as JSON for backup purposes - you can re-import the data later if needed.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
