import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Send, 
  Loader2, 
  Database, 
  Globe, 
  Network, 
  Sparkles,
  Zap
} from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { cn } from '@/lib/utils'

export function ChatInput() {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  const {
    isLoading,
    isStreaming,
    useRag,
    useWebSearch,
    includeGraph,
    setUseRag,
    setUseWebSearch,
    setIncludeGraph,
    streamMessage
  } = useChatStore()

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

  return (
    <div className="border-t border-border/50 bg-card/30 backdrop-blur-sm">
      {/* Options bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border/30">
        <span className="text-xs text-muted-foreground mr-2">Options:</span>
        
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
          RAG
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
          Web Search
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
          Story Graph
        </button>
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="p-4">
        <div className="relative flex items-end gap-3 bg-muted/50 rounded-xl p-3 border border-border/50 focus-within:border-primary/50 transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Discuss your novel, ask about characters, plot ideas..."
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
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  )
}

