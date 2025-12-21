import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Upload, FileText, File, X, Check, AlertCircle, 
  Loader2, FolderOpen, Tag 
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSettingsStore, KNOWLEDGE_CATEGORIES } from '@/store/settingsStore'
import { t } from '@/lib/i18n'

const API_BASE = '/api/v1'

interface UploadResult {
  id: number
  title: string
  category: string
  filename: string
  token_count: number
  chunk_count: number
  tags: string[]
}

export function UploadPage() {
  const { language } = useSettingsStore()
  const [isDragging, setIsDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [category, setCategory] = useState<string>('')
  const [tags, setTags] = useState<string>('')
  const [autoCategize, setAutoCategorize] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])
  const [errors, setErrors] = useState<string[]>([])

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
      file => file.name.endsWith('.pdf') || file.name.endsWith('.docx')
    )
    
    setFiles(prev => [...prev, ...droppedFiles])
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        file => file.name.endsWith('.pdf') || file.name.endsWith('.docx')
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

    const uploadResults: UploadResult[] = []
    const uploadErrors: string[] = []

    for (const file of files) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        if (category) formData.append('category', category)
        formData.append('tags', tags)
        formData.append('auto_categorize', autoCategize.toString())

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
      } catch (error) {
        uploadErrors.push(`${file.name}: ${(error as Error).message}`)
      }
    }

    setResults(uploadResults)
    setErrors(uploadErrors)
    setIsUploading(false)
    
    if (uploadResults.length > 0) {
      setFiles([])
    }
  }

  const getCategoryLabel = (cat: string): string => {
    const key = `knowledge.category.${cat}` as keyof typeof t
    return t(key, language) || cat
  }

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-display font-semibold text-foreground">
          {t('upload.title', language)}
        </h1>
        <p className="text-muted-foreground">
          {t('upload.subtitle', language)}
        </p>
      </div>

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
              accept=".pdf,.docx"
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
                {t('upload.drag_drop', language)}
              </p>
              <p className="text-sm text-muted-foreground">
                {t('upload.supported', language)}
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

          {/* Options */}
          <div className="space-y-4 p-4 rounded-xl bg-card border border-border">
            <div>
              <label className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <FolderOpen className="w-4 h-4" />
                {t('upload.select_category', language)}
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={autoCategize}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary disabled:opacity-50"
              >
                <option value="">Auto-detect</option>
                {KNOWLEDGE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {getCategoryLabel(cat)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <Tag className="w-4 h-4" />
                Tags (comma separated)
              </label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="fantasy, magic, chapter-1"
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
            </div>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoCategize}
                onChange={(e) => setAutoCategorize(e.target.checked)}
                className="w-4 h-4 accent-primary rounded"
              />
              <span className="text-sm text-foreground">
                Auto-categorize based on content
              </span>
            </label>
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
                {t('upload.processing', language)}
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Upload {files.length} file{files.length !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>

        {/* Results */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">Upload Results</h3>

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
                      <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                        {result.chunk_count} chunks
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

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
              <p className="text-sm mt-2">
                Documents will be processed, chunked, and added to your knowledge base
              </p>
            </div>
          )}

          {/* Info */}
          <div className="p-4 rounded-xl bg-card border border-border">
            <h4 className="font-medium text-foreground mb-2">How it works</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Documents are parsed to extract text content</li>
              <li>• Content is auto-categorized (character, plot, settings, etc.)</li>
              <li>• Text is split into chunks for better retrieval</li>
              <li>• Each chunk is embedded and stored in the vector database</li>
              <li>• Content becomes searchable via RAG in chat</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

