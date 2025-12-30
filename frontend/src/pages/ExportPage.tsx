import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Download, FileText, Book, Loader2, Check, 
  BookOpen, Settings, Sparkles
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { storyApi, chaptersApi, type Series, type Chapter } from '@/lib/api'

type ExportFormat = 'markdown' | 'json' | 'txt'

export function ExportPage() {
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('markdown')
  const [includeMetadata, setIncludeMetadata] = useState(true)
  const [includeChapterTitles, setIncludeChapterTitles] = useState(true)
  const [exportComplete, setExportComplete] = useState(false)

  useEffect(() => {
    loadSeries()
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
    const selectedChapters = chapters.filter(c => selectedChapterIds.has(c.id))
    if (selectedChapters.length === 0) return

    setIsExporting(true)
    
    try {
      // Sort by chapter number
      selectedChapters.sort((a, b) => (a.chapter_number || 0) - (b.chapter_number || 0))
      
      let content = ''
      let filename = ''
      let mimeType = ''
      
      const selectedSeriesTitle = series.find(s => s.id === selectedSeriesId)?.title || 'Export'
      
      switch (exportFormat) {
        case 'markdown':
          content = generateMarkdown(selectedChapters, selectedSeriesTitle)
          filename = `${selectedSeriesTitle.replace(/\s+/g, '_')}.md`
          mimeType = 'text/markdown'
          break
        case 'json':
          content = generateJSON(selectedChapters, selectedSeriesTitle)
          filename = `${selectedSeriesTitle.replace(/\s+/g, '_')}.json`
          mimeType = 'application/json'
          break
        case 'txt':
          content = generatePlainText(selectedChapters)
          filename = `${selectedSeriesTitle.replace(/\s+/g, '_')}.txt`
          mimeType = 'text/plain'
          break
      }
      
      // Create and download file
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
    } catch (error) {
      console.error('Export failed:', error)
    } finally {
      setIsExporting(false)
    }
  }

  const generateMarkdown = (chapters: Chapter[], title: string): string => {
    let content = ''
    
    if (includeMetadata) {
      content += `# ${title}\n\n`
      content += `> Exported on ${new Date().toLocaleDateString()}\n\n`
      content += `---\n\n`
    }
    
    for (const chapter of chapters) {
      if (includeChapterTitles) {
        content += `## ${chapter.title}\n\n`
      }
      content += `${chapter.content}\n\n`
      if (includeChapterTitles) {
        content += `---\n\n`
      }
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

  const generatePlainText = (chapters: Chapter[]): string => {
    return chapters.map(c => {
      let text = ''
      if (includeChapterTitles) {
        text += `${c.title}\n${'='.repeat(c.title.length)}\n\n`
      }
      text += c.content
      return text
    }).join('\n\n---\n\n')
  }

  const totalWords = chapters
    .filter(c => selectedChapterIds.has(c.id))
    .reduce((sum, c) => sum + (c.word_count || 0), 0)

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
      <div className="flex-shrink-0 p-6 border-b border-border bg-gradient-to-r from-pink-900/20 to-rose-900/20">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-pink-500/20">
            <Download className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold">Export Center</h1>
            <p className="text-muted-foreground">Export your story in various formats</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Selection */}
          <div className="lg:col-span-2 space-y-6">
            {/* Series Selector */}
            <div className="bg-card border border-border rounded-xl p-4">
              <label className="block text-sm text-muted-foreground mb-2">Select Series</label>
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

            {/* Chapter Selection */}
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-pink-400" />
                  Select Chapters
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    className="text-sm text-pink-400 hover:underline"
                  >
                    Select All
                  </button>
                  <span className="text-muted-foreground">|</span>
                  <button
                    onClick={selectNone}
                    className="text-sm text-pink-400 hover:underline"
                  >
                    Select None
                  </button>
                </div>
              </div>

              {chapters.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No chapters available</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-auto">
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
                      <input
                        type="checkbox"
                        checked={selectedChapterIds.has(chapter.id)}
                        onChange={() => toggleChapter(chapter.id)}
                        className="w-4 h-4 rounded border-border"
                      />
                      <div className="flex-1">
                        <span className="font-medium">{chapter.title}</span>
                        <div className="text-xs text-muted-foreground">
                          Chapter {chapter.chapter_number} • {chapter.word_count} words
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Options & Export */}
          <div className="space-y-6">
            {/* Export Format */}
            <div className="bg-card border border-border rounded-xl p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Settings className="w-5 h-5 text-pink-400" />
                Export Options
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-2">Format</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['markdown', 'json', 'txt'] as ExportFormat[]).map(format => (
                      <button
                        key={format}
                        onClick={() => setExportFormat(format)}
                        className={cn(
                          "px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                          exportFormat === format 
                            ? "bg-pink-500 text-white" 
                            : "bg-muted text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {format === 'markdown' && '.md'}
                        {format === 'json' && '.json'}
                        {format === 'txt' && '.txt'}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeChapterTitles}
                      onChange={(e) => setIncludeChapterTitles(e.target.checked)}
                      className="w-4 h-4 rounded border-border"
                    />
                    <span className="text-sm">Include chapter titles</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeMetadata}
                      onChange={(e) => setIncludeMetadata(e.target.checked)}
                      className="w-4 h-4 rounded border-border"
                    />
                    <span className="text-sm">Include metadata header</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Summary & Export Button */}
            <div className="bg-card border border-border rounded-xl p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Book className="w-5 h-5 text-pink-400" />
                Export Summary
              </h3>

              <div className="space-y-2 mb-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Chapters selected</span>
                  <span className="font-medium">{selectedChapterIds.size}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total words</span>
                  <span className="font-medium">{totalWords.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Format</span>
                  <span className="font-medium uppercase">{exportFormat}</span>
                </div>
              </div>

              <button
                onClick={handleExport}
                disabled={selectedChapterIds.size === 0 || isExporting}
                className={cn(
                  "w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors",
                  exportComplete 
                    ? "bg-green-500 text-white" 
                    : "bg-pink-500 hover:bg-pink-600 text-white disabled:opacity-50"
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
                    Export {selectedChapterIds.size} Chapter{selectedChapterIds.size !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>

            {/* Future Features */}
            <div className="bg-muted/50 border border-dashed border-border rounded-xl p-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <Sparkles className="w-4 h-4" />
                Coming Soon
              </h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• Export to EPUB (e-book format)</li>
                <li>• Export to DOCX (Word document)</li>
                <li>• PDF export with formatting</li>
                <li>• AI-generated synopsis</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


