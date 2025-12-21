import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, X, Loader2, Check, AlertCircle } from 'lucide-react'
import { useSettingsStore } from '@/store/settingsStore'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

interface DocumentUploadProps {
  onUpload: (content: string, filename: string) => void
  onClose: () => void
  mode?: 'chat' | 'knowledge'
  category?: string
}

const KNOWLEDGE_CATEGORIES = [
  'draft', 'concept', 'character', 'chapter', 
  'settings', 'worldbuilding', 'plot', 'dialogue', 'research', 'other'
]

export function DocumentUpload({ onUpload, onClose, mode = 'chat', category = 'other' }: DocumentUploadProps) {
  const { language } = useSettingsStore()
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [selectedCategory, setSelectedCategory] = useState(category)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = e.dataTransfer.files
    if (files.length > 0) {
      await uploadFile(files[0])
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      await uploadFile(files[0])
    }
  }

  const uploadFile = async (file: File) => {
    // Validate file type
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    const validExtensions = ['.pdf', '.docx', '.txt']
    
    const isValidType = validTypes.includes(file.type) || validExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
    
    if (!isValidType) {
      setUploadStatus('error')
      setErrorMessage('Please upload a PDF, DOCX, or TXT file')
      return
    }

    // Validate file size (50MB max)
    if (file.size > 50 * 1024 * 1024) {
      setUploadStatus('error')
      setErrorMessage('File too large. Maximum size is 50MB')
      return
    }

    setIsUploading(true)
    setUploadStatus('idle')
    setErrorMessage('')

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('language', language)
      
      if (mode === 'knowledge') {
        formData.append('category', selectedCategory)
        
        const response = await fetch('/api/v1/documents/upload', {
          method: 'POST',
          body: formData,
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Upload failed')
        }
        
        const result = await response.json()
        setUploadStatus('success')
        
        setTimeout(() => {
          onUpload(result.message, file.name)
          onClose()
        }, 1000)
      } else {
        // For chat mode, just parse the document
        const response = await fetch('/api/v1/documents/upload-to-chat', {
          method: 'POST',
          body: formData,
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Upload failed')
        }
        
        const result = await response.json()
        setUploadStatus('success')
        
        setTimeout(() => {
          onUpload(result.full_content, file.name)
          onClose()
        }, 1000)
      }
    } catch (error) {
      setUploadStatus('error')
      setErrorMessage((error as Error).message)
    } finally {
      setIsUploading(false)
    }
  }

  const categoryLabels: Record<string, Record<string, string>> = {
    en: {
      draft: 'Draft', concept: 'Concept', character: 'Character',
      chapter: 'Chapter', settings: 'Settings', worldbuilding: 'World Building',
      plot: 'Plot', dialogue: 'Dialogue', research: 'Research', other: 'Other'
    },
    'zh-TW': {
      draft: '草稿', concept: '概念', character: '角色',
      chapter: '章節', settings: '設定', worldbuilding: '世界觀',
      plot: '情節', dialogue: '對話', research: '研究', other: '其他'
    },
    'zh-CN': {
      draft: '草稿', concept: '概念', character: '角色',
      chapter: '章节', settings: '设定', worldbuilding: '世界观',
      plot: '情节', dialogue: '对话', research: '研究', other: '其他'
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-card border border-border rounded-xl p-6 w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-display font-semibold text-foreground">
            {t('uploadTitle', language)}
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-muted rounded">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {mode === 'knowledge' && (
          <div className="mb-4">
            <label className="block text-sm text-muted-foreground mb-2">
              {t('category', language)}
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
            >
              {KNOWLEDGE_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {categoryLabels[language]?.[cat] || cat}
                </option>
              ))}
            </select>
          </div>
        )}

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
            isDragging
              ? "border-primary bg-primary/10"
              : "border-border hover:border-primary/50 hover:bg-muted/50",
            isUploading && "pointer-events-none opacity-50"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />
          
          <AnimatePresence mode="wait">
            {isUploading ? (
              <motion.div
                key="uploading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center"
              >
                <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
                <p className="text-foreground">{t('loading', language)}</p>
              </motion.div>
            ) : uploadStatus === 'success' ? (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center"
              >
                <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mb-4">
                  <Check className="w-6 h-6 text-green-500" />
                </div>
                <p className="text-green-500">{t('uploadSuccess', language)}</p>
              </motion.div>
            ) : uploadStatus === 'error' ? (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center"
              >
                <div className="w-12 h-12 rounded-full bg-destructive/20 flex items-center justify-center mb-4">
                  <AlertCircle className="w-6 h-6 text-destructive" />
                </div>
                <p className="text-destructive mb-2">{t('uploadError', language)}</p>
                <p className="text-sm text-muted-foreground">{errorMessage}</p>
              </motion.div>
            ) : (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center"
              >
                <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center mb-4">
                  <Upload className="w-6 h-6 text-primary" />
                </div>
                <p className="text-foreground mb-2">{t('uploadDragDrop', language)}</p>
                <p className="text-sm text-muted-foreground">{t('uploadSupported', language)}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  )
}

