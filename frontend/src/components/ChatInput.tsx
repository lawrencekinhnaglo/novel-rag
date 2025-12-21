import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Send, 
  Loader2, 
  Database, 
  Globe, 
  Network, 
  Upload,
  X,
  FileText,
  Languages
} from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { useSettingsStore } from '@/store/settingsStore'
import { DocumentUpload } from './DocumentUpload'
import { LANGUAGES, t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export function ChatInput() {
  const [input, setInput] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [showLanguageMenu, setShowLanguageMenu] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  const {
    isLoading,
    isStreaming,
    useRag,
    useWebSearch,
    includeGraph,
    uploadedFilename,
    setUseRag,
    setUseWebSearch,
    setIncludeGraph,
    setUploadedContent,
    streamMessage
  } = useChatStore()
  
  const { language, setLanguage } = useSettingsStore()

  const isProcessing = isLoading || isStreaming

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isProcessing) return
    
    const message = input.trim()
    setInput('')
    await streamMessage(message)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleUpload = (content: string, filename: string) => {
    setUploadedContent(content, filename)
    setShowUpload(false)
  }

  return (
    <div className="border-t border-border/50 bg-card/30 backdrop-blur-sm">
      {/* Upload modal */}
      <AnimatePresence>
        {showUpload && (
          <DocumentUpload 
            onUpload={handleUpload}
            onClose={() => setShowUpload(false)}
            mode="chat"
          />
        )}
      </AnimatePresence>

      {/* Uploaded file indicator */}
      {uploadedFilename && (
        <div className="flex items-center gap-2 px-4 py-2 bg-primary/10 border-b border-primary/20">
          <FileText className="w-4 h-4 text-primary" />
          <span className="text-sm text-primary flex-1">{uploadedFilename}</span>
          <button
            onClick={() => setUploadedContent(null, null)}
            className="p-1 hover:bg-primary/20 rounded"
          >
            <X className="w-4 h-4 text-primary" />
          </button>
        </div>
      )}

      {/* Options bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border/30 flex-wrap">
        <span className="text-xs text-muted-foreground mr-2">{t('optionsLabel', language)}</span>
        
        <button
          onClick={() => setUseRag(!useRag)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all",
            useRag 
              ? "bg-primary/20 text-primary" 
              : "bg-muted/50 text-muted-foreground hover:bg-muted"
          )}
        >
          <Database className="w-3 h-3" />
          {t('optionRAG', language)}
        </button>
        
        <button
          onClick={() => setUseWebSearch(!useWebSearch)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all",
            useWebSearch 
              ? "bg-blue-500/20 text-blue-400" 
              : "bg-muted/50 text-muted-foreground hover:bg-muted"
          )}
        >
          <Globe className="w-3 h-3" />
          {t('optionWebSearch', language)}
        </button>
        
        <button
          onClick={() => setIncludeGraph(!includeGraph)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all",
            includeGraph 
              ? "bg-green-500/20 text-green-400" 
              : "bg-muted/50 text-muted-foreground hover:bg-muted"
          )}
        >
          <Network className="w-3 h-3" />
          {t('optionGraph', language)}
        </button>

        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-muted/50 text-muted-foreground hover:bg-muted transition-all"
        >
          <Upload className="w-3 h-3" />
          {t('uploadButton', language)}
        </button>

        <div className="flex-1" />

        {/* Language selector */}
        <div className="relative">
          <button
            onClick={() => setShowLanguageMenu(!showLanguageMenu)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-muted/50 text-muted-foreground hover:bg-muted transition-all"
          >
            <Languages className="w-3 h-3" />
            {LANGUAGES[language]}
          </button>
          <AnimatePresence>
            {showLanguageMenu && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                className="absolute bottom-full right-0 mb-1 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-10"
              >
                {(Object.keys(LANGUAGES) as Array<keyof typeof LANGUAGES>).map((lang) => (
                  <button
                    key={lang}
                    onClick={() => {
                      setLanguage(lang)
                      setShowLanguageMenu(false)
                    }}
                    className={cn(
                      "block w-full px-4 py-2 text-left text-sm hover:bg-muted transition-colors",
                      lang === language && "bg-primary/10 text-primary"
                    )}
                  >
                    {LANGUAGES[lang]}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="p-4">
        <div className="relative flex items-end gap-3 bg-muted/50 rounded-xl p-3 border border-border/50 focus-within:border-primary/50 transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chatPlaceholder', language)}
            className="flex-1 bg-transparent resize-none outline-none text-foreground placeholder:text-muted-foreground min-h-[24px] max-h-[200px]"
            rows={1}
            disabled={isProcessing}
          />
          
          <motion.button
            type="submit"
            disabled={!input.trim() || isProcessing}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={cn(
              "flex items-center justify-center w-10 h-10 rounded-lg transition-all",
              input.trim() && !isProcessing
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            {isProcessing ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </motion.button>
        </div>
        
        <p className="text-xs text-muted-foreground mt-2 text-center">
          {t('chatPressEnter', language)}
        </p>
      </form>
    </div>
  )
}

