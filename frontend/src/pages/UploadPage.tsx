import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, File, X, Check, AlertCircle,
  Loader2, FolderOpen, Tag, Sparkles, Users, Globe, Lightbulb,
  ArrowRight, BookOpen, Scroll, Swords, Map, Wand2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSettingsStore, KNOWLEDGE_CATEGORIES } from '@/store/settingsStore'
import { t } from '@/lib/i18n'
import { storyApi, type Series } from '@/lib/api'
import { useEffect } from 'react'

const API_BASE = '/api/v1'

type UploadMode = 'standard' | 'worldbuilding' | 'smart' | 'raw'

interface ExtractionResult {
  total_extracted: number
  characters: Array<{ id: number; name: string; confidence?: number }>
  world_rules: Array<{ id: number; name: string; confidence?: number }>
  foreshadowing: Array<{ id: number; name: string; confidence?: number }>
  locations: Array<{ id: number; name: string; confidence?: number }>
  facts: Array<{ id: number; description?: string; confidence?: number }>
  story_parts?: Array<{ id: number; title?: string }>
  concepts?: Array<{ id: number; name?: string }>
  cultivation_system?: boolean
  series: number | null
  status?: string
  message?: string
  errors?: string[]
}

interface UploadResult {
  id: number
  title: string
  category: string
  filename: string
  token_count: number
  chunk_count: number
  tags: string[]
  extraction?: ExtractionResult | null
}

interface WorldbuildingResult {
  status: string
  filename: string
  token_count: number
  document?: {
    title: string
    version: string
  }
  extraction_summary?: {
    main_story_parts: number
    spinoffs: number
    prequels: number
    characters: number
    cultivation_realms: number
    artifacts: number
    foreshadowing: number
    world_rules: number
  }
  database_result?: {
    series_id: number
    books_created: Array<{ id: number; title: string }>
    characters_created: Array<{ id: number; name: string }>
    errors: string[]
  }
  details?: {
    main_story: Array<{ part_number: number; title: string; protagonists: string[] }>
    characters: Array<{ name: string; role: string; generation: string }>
    artifacts: Array<{ name: string; type: string }>
    cultivation_realms: Array<{ tier: number; name: string; group: string }>
  }
  message?: string
}

export function UploadPage() {
  const { language } = useSettingsStore()
  const [isDragging, setIsDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | undefined>()
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [uploadMode, setUploadMode] = useState<UploadMode>('standard')
  const [worldbuildingResult, setWorldbuildingResult] = useState<WorldbuildingResult | null>(null)

  // Load series on mount
  useEffect(() => {
    loadSeries()
  }, [])

  const loadSeries = async () => {
    try {
      const series = await storyApi.listSeries()
      setSeriesList(series)
    } catch (err) {
      console.error('Failed to load series:', err)
    }
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.name.endsWith('.pdf') || file.name.endsWith('.docx') || file.name.endsWith('.txt')
    )

    setFiles(prev => [...prev, ...droppedFiles])
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        file => file.name.endsWith('.pdf') || file.name.endsWith('.docx') || file.name.endsWith('.txt')
      )
      setFiles(prev => [...prev, ...selectedFiles])
    }
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setIsUploading(true)
    setResults([])
    setErrors([])
    setWorldbuildingResult(null)

    const uploadResults: UploadResult[] = []
    const uploadErrors: string[] = []

    for (const file of files) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        
        if (uploadMode === 'smart') {
          // Smart import - AI classifies but preserves original text
          if (selectedSeriesId) {
            formData.append('series_id', selectedSeriesId.toString())
          }

          const response = await fetch(`${API_BASE}/worldbuilding/smart-import`, {
            method: 'POST',
            body: formData
          })

          if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || 'Smart import failed')
          }

          const result = await response.json()
          setWorldbuildingResult({
            status: 'success',
            filename: result.filename,
            token_count: result.total_characters,
            document: {
              title: result.filename,
              version: 'Smart Import'
            },
            extraction_summary: {
              main_story_parts: 0,
              spinoffs: 0,
              prequels: 0,
              characters: result.categories?.character || 0,
              cultivation_realms: result.categories?.cultivation || 0,
              artifacts: result.categories?.artifact || 0,
              foreshadowing: result.categories?.foreshadowing || 0,
              world_rules: result.categories?.world_rule || 0
            },
            database_result: {
              series_id: result.series_id,
              books_created: [],
              characters_created: [],
              errors: []
            },
            message: result.message,
            details: {
              main_story: [],
              characters: [],
              artifacts: [],
              cultivation_realms: []
            }
          })
        } else if (uploadMode === 'worldbuilding') {
          // Use worldbuilding parser endpoint (AI interpretation)
          formData.append('save_to_database', 'true')
          if (selectedSeriesId) {
            formData.append('series_id', selectedSeriesId.toString())
          }

          const response = await fetch(`${API_BASE}/worldbuilding/parse`, {
            method: 'POST',
            body: formData
          })

          if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || 'Worldbuilding parse failed')
          }

          const result = await response.json()
          setWorldbuildingResult(result)
        } else if (uploadMode === 'raw') {
          // Raw import - no AI interpretation, preserves exact text
          if (selectedSeriesId) {
            formData.append('series_id', selectedSeriesId.toString())
          }

          const response = await fetch(`${API_BASE}/worldbuilding/raw-import`, {
            method: 'POST',
            body: formData
          })

          if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || 'Raw import failed')
          }

          const result = await response.json()
          setWorldbuildingResult({
            status: 'success',
            filename: result.filename,
            series_id: result.series_id,
            summary: {
              title: result.filename,
              total_sections: result.sections_saved,
              message: result.message
            }
          })
        } else {
          // Standard upload
          formData.append('auto_categorize', 'true')
          formData.append('extract_story_elements', 'true')
          if (selectedSeriesId) {
            formData.append('series_id', selectedSeriesId.toString())
          }

          const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
          })

          if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || 'Upload failed')
          }

          const result = await response.json()
          uploadResults.push(result)
        }
      } catch (error) {
        uploadErrors.push(`${file.name}: ${(error as Error).message}`)
      }
    }

    setResults(uploadResults)
    setErrors(uploadErrors)
    setIsUploading(false)

    if (uploadResults.length > 0 || worldbuildingResult) {
      setFiles([])
    }
  }

  const hasExtractionResults = results.some(r => r.extraction && r.extraction.total_extracted > 0)

  return (
    <div className="h-full flex flex-col p-6 overflow-y-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-display font-semibold text-foreground">
          {t('uploadTitle', language)}
        </h1>
        <p className="text-muted-foreground">
          Upload your story documents - characters, world rules, and story elements will be automatically extracted
        </p>
      </div>

      {/* Upload Mode Selector */}
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setUploadMode('standard')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors",
            uploadMode === 'standard'
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-card border-border hover:border-primary/50"
          )}
        >
          <FileText className="w-4 h-4" />
          <span>Standard</span>
        </button>
        <button
          onClick={() => setUploadMode('smart')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors",
            uploadMode === 'smart'
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-card border-border hover:border-blue-500/50"
          )}
        >
          <Sparkles className="w-4 h-4" />
          <span>Smart Import</span>
          <span className="px-1.5 py-0.5 text-xs rounded bg-blue-500/20 text-blue-300">Recommended</span>
        </button>
        <button
          onClick={() => setUploadMode('worldbuilding')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors",
            uploadMode === 'worldbuilding'
              ? "bg-purple-600 text-white border-purple-600"
              : "bg-card border-border hover:border-purple-500/50"
          )}
        >
          <Wand2 className="w-4 h-4" />
          <span>AI Rewrite</span>
          <span className="px-1.5 py-0.5 text-xs rounded bg-purple-500/20 text-purple-300">Pro</span>
        </button>
        <button
          onClick={() => setUploadMode('raw')}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors",
            uploadMode === 'raw'
              ? "bg-green-600 text-white border-green-600"
              : "bg-card border-border hover:border-green-500/50"
          )}
        >
          <FileText className="w-4 h-4" />
          <span>Raw Import</span>
        </button>
      </div>

      {/* Smart Import Mode Info */}
      {uploadMode === 'smart' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/30"
        >
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-blue-400 mt-0.5" />
            <div>
              <h3 className="font-medium text-blue-400 mb-1">Smart Import (Recommended)</h3>
              <p className="text-sm text-muted-foreground mb-3">
                AI parses and classifies your document sections WITHOUT altering the original text.
              </p>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  <span>Preserves your exact text - no AI rewriting</span>
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  <span>AI classifies each section (character, world_rule, artifact, etc.)</span>
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  <span>Creates editable items in Knowledge Base</span>
                </li>
                <li className="flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-purple-400" />
                  <span>Ask AI to improve individual items later</span>
                </li>
              </ul>
            </div>
          </div>
        </motion.div>
      )}

      {/* Worldbuilding AI Rewrite Mode Info */}
      {uploadMode === 'worldbuilding' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-purple-500/10 border border-purple-500/30"
        >
          <div className="flex items-start gap-3">
            <Wand2 className="w-5 h-5 text-purple-400 mt-0.5" />
            <div>
              <h3 className="font-medium text-purple-300 mb-1">AI 專業設定文檔解析</h3>
              <p className="text-sm text-muted-foreground mb-2">
                AI extracts and interprets worldbuilding elements
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <BookOpen className="w-3 h-3" /> Story parts (正傳/外傳/前傳)
                </div>
                <div className="flex items-center gap-1">
                  <Users className="w-3 h-3" /> Characters by generation
                </div>
                <div className="flex items-center gap-1">
                  <Swords className="w-3 h-3" /> Cultivation systems (十五境)
                </div>
                <div className="flex items-center gap-1">
                  <Map className="w-3 h-3" /> World maps & artifacts
                </div>
              </div>
              <p className="text-xs text-amber-400 mt-2">⚠️ AI may interpret/summarize content</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Raw Import Mode Info */}
      {uploadMode === 'raw' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-green-500/10 border border-green-500/30"
        >
          <div className="flex items-start gap-3">
            <FileText className="w-5 h-5 text-green-400 mt-0.5" />
            <div>
              <h3 className="font-medium text-green-300 mb-1">原文直接導入 (Raw Import)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Import your document EXACTLY as written - NO AI modification
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-1 text-green-300">
                  ✓ Preserves exact text
                </div>
                <div className="flex items-center gap-1 text-green-300">
                  ✓ No AI summarization
                </div>
                <div className="flex items-center gap-1 text-green-300">
                  ✓ Splits by numbered sections
                </div>
                <div className="flex items-center gap-1 text-green-300">
                  ✓ Direct to knowledge base
                </div>
              </div>
              <p className="text-xs text-green-400 mt-2">✅ Recommended for preserving your exact worldbuilding</p>
            </div>
          </div>
        </motion.div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Upload Area */}
        <div className="space-y-6">
          {/* Drop Zone */}
          <motion.div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              "relative border-2 border-dashed rounded-xl p-12 text-center transition-colors",
              isDragging
                ? "border-primary bg-primary/10"
                : "border-border hover:border-primary/50"
            )}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt"
              onChange={handleFileSelect}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center">
              <motion.div
                animate={{ y: isDragging ? -5 : 0 }}
                className="w-16 h-16 rounded-xl bg-primary/20 flex items-center justify-center mb-4"
              >
                <Upload className="w-8 h-8 text-primary" />
              </motion.div>
              <p className="text-foreground font-medium mb-2">
                {t('uploadDragDrop', language)}
              </p>
              <p className="text-sm text-muted-foreground">
                {t('uploadSupported', language)}
              </p>
            </div>
          </motion.div>

          {/* Selected Files */}
          <AnimatePresence>
            {files.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-2"
              >
                <p className="text-sm text-muted-foreground">
                  Selected files ({files.length}):
                </p>
                {files.map((file, index) => (
                  <motion.div
                    key={`${file.name}-${index}`}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    className="flex items-center justify-between p-3 rounded-lg bg-card border border-border"
                  >
                    <div className="flex items-center gap-3">
                      {file.name.endsWith('.pdf') ? (
                        <File className="w-5 h-5 text-red-400" />
                      ) : file.name.endsWith('.txt') ? (
                        <FileText className="w-5 h-5 text-gray-400" />
                      ) : (
                        <FileText className="w-5 h-5 text-blue-400" />
                      )}
                      <div>
                        <p className="text-sm font-medium text-foreground">{file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="p-1 hover:bg-muted rounded transition-colors"
                    >
                      <X className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Series Selection */}
          <div className="p-4 rounded-xl bg-card border border-border">
            <div>
              <label className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <BookOpen className="w-4 h-4" />
                Link to Series (optional)
              </label>
              <select
                value={selectedSeriesId || ''}
                onChange={(e) => setSelectedSeriesId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
              >
                <option value="">Auto-detect or create new</option>
                {seriesList.map((series) => (
                  <option key={series.id} value={series.id}>
                    {series.title}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground mt-2">
                Extracted elements will be linked to this series
              </p>
            </div>
          </div>

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={files.length === 0 || isUploading}
            className={cn(
              "w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors",
              files.length > 0 && !isUploading
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            {isUploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {uploadMode === 'worldbuilding' ? 'Parsing Worldbuilding...' 
                  : uploadMode === 'raw' ? 'Importing Raw...' 
                  : 'Uploading & Extracting...'}
              </>
            ) : (
              <>
                {uploadMode === 'worldbuilding' ? <Scroll className="w-5 h-5" /> 
                  : uploadMode === 'raw' ? <FileText className="w-5 h-5" /> 
                  : <Upload className="w-5 h-5" />}
                {uploadMode === 'worldbuilding' 
                  ? `Parse Worldbuilding Document` 
                  : uploadMode === 'raw'
                  ? `Raw Import Document`
                  : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
              </>
            )}
          </button>
        </div>

        {/* Results */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">Results</h3>

          {/* Worldbuilding Results */}
          {worldbuildingResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/30"
            >
              <div className="flex items-start gap-3 mb-4">
                <Scroll className="w-5 h-5 text-purple-400 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-foreground">
                    {worldbuildingResult.document?.title || 'Worldbuilding Document'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {worldbuildingResult.filename} • {worldbuildingResult.token_count?.toLocaleString()} tokens
                  </p>
                </div>
                {worldbuildingResult.status === 'completed' && (
                  <Check className="w-5 h-5 text-green-400" />
                )}
                {worldbuildingResult.status === 'processing' && (
                  <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
                )}
              </div>

              {worldbuildingResult.extraction_summary && (
                <div className="grid grid-cols-4 gap-2 mb-4">
                  <div className="p-2 rounded-lg bg-blue-500/10 text-center">
                    <div className="text-lg font-bold text-blue-400">
                      {worldbuildingResult.extraction_summary.main_story_parts + 
                       worldbuildingResult.extraction_summary.spinoffs +
                       worldbuildingResult.extraction_summary.prequels}
                    </div>
                    <div className="text-xs text-muted-foreground">Books</div>
                  </div>
                  <div className="p-2 rounded-lg bg-green-500/10 text-center">
                    <div className="text-lg font-bold text-green-400">
                      {worldbuildingResult.extraction_summary.characters}
                    </div>
                    <div className="text-xs text-muted-foreground">Characters</div>
                  </div>
                  <div className="p-2 rounded-lg bg-yellow-500/10 text-center">
                    <div className="text-lg font-bold text-yellow-400">
                      {worldbuildingResult.extraction_summary.cultivation_realms}
                    </div>
                    <div className="text-xs text-muted-foreground">Realms</div>
                  </div>
                  <div className="p-2 rounded-lg bg-purple-500/10 text-center">
                    <div className="text-lg font-bold text-purple-400">
                      {worldbuildingResult.extraction_summary.artifacts}
                    </div>
                    <div className="text-xs text-muted-foreground">Artifacts</div>
                  </div>
                </div>
              )}

              {worldbuildingResult.details?.main_story && (
                <div className="mb-3">
                  <p className="text-xs text-muted-foreground mb-1">Story Parts:</p>
                  <div className="flex flex-wrap gap-1">
                    {worldbuildingResult.details.main_story.map((part, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-xs">
                        Part {part.part_number}: {part.title}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {worldbuildingResult.details?.characters && worldbuildingResult.details.characters.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-muted-foreground mb-1">Characters ({worldbuildingResult.details.characters.length}):</p>
                  <div className="flex flex-wrap gap-1">
                    {worldbuildingResult.details.characters.slice(0, 12).map((char, i) => (
                      <span key={i} className={cn(
                        "px-2 py-0.5 rounded text-xs",
                        char.role === 'protagonist' ? "bg-green-500/20 text-green-300" :
                        char.role === 'antagonist' ? "bg-red-500/20 text-red-300" :
                        "bg-gray-500/20 text-gray-300"
                      )}>
                        {char.name} ({char.generation || char.role})
                      </span>
                    ))}
                    {worldbuildingResult.details.characters.length > 12 && (
                      <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                        +{worldbuildingResult.details.characters.length - 12} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {worldbuildingResult.message && (
                <p className="text-sm text-green-400 mt-2">{worldbuildingResult.message}</p>
              )}

              {worldbuildingResult.database_result?.errors && worldbuildingResult.database_result.errors.length > 0 && (
                <div className="mt-2 p-2 rounded bg-yellow-500/10 border border-yellow-500/30">
                  <p className="text-xs text-yellow-400">
                    {worldbuildingResult.database_result.errors.length} warnings during save
                  </p>
                </div>
              )}
            </motion.div>
          )}

          {/* Success Results */}
          <AnimatePresence>
            {results.map((result, index) => (
              <motion.div
                key={result.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="p-4 rounded-xl bg-green-500/10 border border-green-500/30"
              >
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-green-400 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium text-foreground">{result.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {result.filename}
                    </p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      <span className="px-2 py-0.5 rounded bg-primary/20 text-primary text-xs">
                        {result.category}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                        {result.token_count.toLocaleString()} tokens
                      </span>
                    </div>

                    {/* Extraction Results */}
                    {result.extraction && (
                      <div className="mt-4 p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                        <div className="flex items-center gap-2 mb-2">
                          <Sparkles className="w-4 h-4 text-purple-400" />
                          <span className="text-sm font-medium text-purple-300">
                            Story Elements Extracted
                          </span>
                        </div>

                        {result.extraction.status === 'processing' ? (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            {result.extraction.message}
                          </div>
                        ) : (
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            {(result.extraction.characters?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <Users className="w-3 h-3 text-blue-400" />
                                <span>{result.extraction.characters?.length} Characters</span>
                              </div>
                            )}
                            {(result.extraction.world_rules?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <Globe className="w-3 h-3 text-green-400" />
                                <span>{result.extraction.world_rules?.length} World Rules</span>
                              </div>
                            )}
                            {(result.extraction.story_parts?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <BookOpen className="w-3 h-3 text-orange-400" />
                                <span>{result.extraction.story_parts?.length} Story Parts</span>
                              </div>
                            )}
                            {(result.extraction.concepts?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <Lightbulb className="w-3 h-3 text-yellow-400" />
                                <span>{result.extraction.concepts?.length} Concepts</span>
                              </div>
                            )}
                            {(result.extraction.foreshadowing?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <Sparkles className="w-3 h-3 text-purple-400" />
                                <span>{result.extraction.foreshadowing?.length} Foreshadowing</span>
                              </div>
                            )}
                            {(result.extraction.facts?.length || 0) > 0 && (
                              <div className="flex items-center gap-1">
                                <Lightbulb className="w-3 h-3 text-yellow-400" />
                                <span>{result.extraction.facts?.length} Facts</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Go to Verification Button */}
          {hasExtractionResults && (
            <motion.a
              href="/verification"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg bg-purple-500 text-white font-medium hover:bg-purple-600 transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
              Review Extracted Elements in Verification Hub
            </motion.a>
          )}

          {/* Errors */}
          <AnimatePresence>
            {errors.map((error, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 rounded-xl bg-destructive/10 border border-destructive/30"
              >
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
                  <p className="text-sm text-destructive">{error}</p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {results.length === 0 && errors.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Upload documents to see results here</p>
            </div>
          )}

          {/* How it works */}
          <div className="p-4 rounded-xl bg-card border border-border">
            <h4 className="font-medium text-foreground mb-3">How it works</h4>
            <ul className="text-sm text-muted-foreground space-y-2">
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                <span>Upload your story documents (PDF, DOCX, TXT)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                <span>AI automatically extracts characters, world rules, and story elements</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                <span>Review and approve extracted items in the Verification Hub</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center flex-shrink-0 mt-0.5">4</span>
                <span>Use verified elements to maintain story consistency</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
