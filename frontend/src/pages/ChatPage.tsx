import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Feather, Sparkles, BookOpen, Save } from 'lucide-react'
import { ChatSidebar } from '@/components/ChatSidebar'
import { ChatMessage } from '@/components/ChatMessage'
import { ChatInput } from '@/components/ChatInput'
import { useChatStore } from '@/store/chatStore'
import { knowledgeApi } from '@/lib/api'

export function ChatPage() {
  const { messages, currentSessionId, isStreaming, error, clearError } = useChatStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSaveAsKnowledge = async () => {
    if (!currentSessionId) return
    try {
      await knowledgeApi.fromChat(currentSessionId, undefined, ['chat-saved'])
      alert('Chat saved to knowledge base!')
    } catch (error) {
      console.error('Failed to save chat:', error)
    }
  }

  return (
    <div className="flex h-full">
      {/* Chat sidebar */}
      <ChatSidebar />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
          <div>
            <h2 className="text-lg font-display font-semibold text-foreground">
              {currentSessionId ? 'Novel Discussion' : 'Start a New Conversation'}
            </h2>
            <p className="text-sm text-muted-foreground">
              Discuss your story with AI-powered context awareness
            </p>
          </div>
          {currentSessionId && messages.length > 0 && (
            <button
              onClick={handleSaveAsKnowledge}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent transition-colors"
            >
              <Save className="w-4 h-4" />
              <span className="text-sm font-medium">Save to Knowledge</span>
            </button>
          )}
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
                <p className="text-sm text-destructive">{error}</p>
                <button
                  onClick={clearError}
                  className="text-xs text-destructive hover:underline"
                >
                  Dismiss
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center max-w-md"
              >
                <motion.div
                  animate={{ rotate: [0, 10, -10, 0] }}
                  transition={{ duration: 4, repeat: Infinity }}
                  className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center"
                >
                  <Feather className="w-10 h-10 text-primary" />
                </motion.div>
                <h3 className="text-xl font-display font-semibold text-foreground mb-3">
                  Welcome to Novel RAG
                </h3>
                <p className="text-muted-foreground mb-6">
                  I'm your AI writing assistant with memory. I can help you with:
                </p>
                <div className="grid gap-3 text-left">
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-card/50">
                    <Sparkles className="w-5 h-5 text-primary mt-0.5" />
                    <div>
                      <p className="font-medium text-foreground">Plot & Character Development</p>
                      <p className="text-sm text-muted-foreground">Discuss story ideas and character arcs</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-card/50">
                    <BookOpen className="w-5 h-5 text-accent mt-0.5" />
                    <div>
                      <p className="font-medium text-foreground">Context-Aware Conversations</p>
                      <p className="text-sm text-muted-foreground">I remember your chapters, characters, and timeline</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          ) : (
            <div className="space-y-4">
              <AnimatePresence>
                {messages.map((message, index) => (
                  <ChatMessage 
                    key={message.id} 
                    message={message}
                    isStreaming={isStreaming && index === messages.length - 1 && message.role === 'assistant'}
                  />
                ))}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <ChatInput />
      </div>
    </div>
  )
}

