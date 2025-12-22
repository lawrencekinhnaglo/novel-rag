import { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { User, Bot, Sparkles, Globe, BookOpen, Save, Check, Copy, Loader2, Wand2, UserPlus, BookMarked, Lightbulb, Search, FileText, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'
import { knowledgeApi, type Message } from '@/lib/api'

// Intent type icons and colors
const intentConfig: Record<string, { icon: React.ComponentType<{ className?: string }>, color: string, label: string }> = {
  'chat': { icon: Brain, color: 'bg-blue-500/20 text-blue-400', label: 'Chat' },
  'write_chapter': { icon: FileText, color: 'bg-green-500/20 text-green-400', label: 'Write Chapter' },
  'write_scene': { icon: FileText, color: 'bg-green-500/20 text-green-400', label: 'Write Scene' },
  'continue_story': { icon: Wand2, color: 'bg-purple-500/20 text-purple-400', label: 'Continue Story' },
  'write_dialogue': { icon: FileText, color: 'bg-green-500/20 text-green-400', label: 'Dialogue' },
  'create_character': { icon: UserPlus, color: 'bg-amber-500/20 text-amber-400', label: 'Create Character' },
  'update_character': { icon: UserPlus, color: 'bg-amber-500/20 text-amber-400', label: 'Update Character' },
  'create_world_rule': { icon: BookMarked, color: 'bg-cyan-500/20 text-cyan-400', label: 'World Rule' },
  'create_foreshadowing': { icon: Lightbulb, color: 'bg-yellow-500/20 text-yellow-400', label: 'Foreshadowing' },
  'analyze_consistency': { icon: Search, color: 'bg-red-500/20 text-red-400', label: 'Consistency Check' },
  'query_character': { icon: UserPlus, color: 'bg-amber-500/20 text-amber-400', label: 'Character Query' },
  'query_plot': { icon: BookMarked, color: 'bg-cyan-500/20 text-cyan-400', label: 'Plot Query' },
  'save_to_knowledge': { icon: Save, color: 'bg-primary/20 text-primary', label: 'Save Knowledge' },
}

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
  sessionId?: string  // Session ID for linking saved messages
}

export function ChatMessage({ message, isStreaming, sessionId }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const sources = message.metadata?.sources as Array<{ type: string; title: string; url?: string }> | undefined
  const detectedIntent = message.metadata?.detected_intent as { type: string; confidence: number } | undefined
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleSaveToKnowledge = async () => {
    setIsSaving(true)
    try {
      // Use the new API that links to session if available
      if (sessionId) {
        await knowledgeApi.saveMessage(
          sessionId,
          message.content,
          `AI Response - ${new Date().toLocaleDateString()}`,
          ['ai-response', 'saved-from-chat']
        )
      } else {
        // Fallback to regular create
        await knowledgeApi.create({
          source_type: 'chat',
          title: `AI Response - ${new Date().toLocaleDateString()}`,
          content: message.content,
          tags: ['ai-response', 'saved-from-chat']
        })
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (error) {
      console.error('Failed to save to knowledge:', error)
      alert('Failed to save to knowledge base')
    } finally {
      setIsSaving(false)
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-4 p-4 rounded-xl group",
        isUser ? "bg-transparent" : "bg-card/50"
      )}
    >
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
        isUser ? "bg-accent/20" : "bg-primary/20"
      )}>
        {isUser ? (
          <User className="w-4 h-4 text-accent" />
        ) : (
          <Bot className="w-4 h-4 text-primary" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-sm font-medium",
              isUser ? "text-accent" : "text-primary"
            )}>
              {isUser ? 'You' : 'Novel AI'}
            </span>
            {!isUser && isStreaming && (
              <motion.div
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="flex items-center gap-1 text-xs text-primary"
              >
                <Sparkles className="w-3 h-3" />
                <span>Writing...</span>
              </motion.div>
            )}
            {/* Intent badge */}
            {!isUser && detectedIntent && detectedIntent.type !== 'chat' && (
              (() => {
                const config = intentConfig[detectedIntent.type] || intentConfig['chat']
                const IconComponent = config.icon
                return (
                  <span className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                    config.color
                  )}>
                    <IconComponent className="w-3 h-3" />
                    {config.label}
                    <span className="opacity-60">
                      {Math.round(detectedIntent.confidence * 100)}%
                    </span>
                  </span>
                )
              })()
            )}
          </div>
          
          {/* Action buttons for AI messages */}
          {!isUser && !isStreaming && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleCopy}
                className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                title="Copy to clipboard"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={handleSaveToKnowledge}
                disabled={isSaving || saved}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  saved 
                    ? "text-green-500" 
                    : "hover:bg-muted text-muted-foreground hover:text-foreground"
                )}
                title="Save to Knowledge Base"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : saved ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
              </button>
            </div>
          )}
        </div>

        {/* Message content */}
        <div className="prose-novel">
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
              em: ({ children }) => <em className="italic">{children}</em>,
              code: ({ children, className }) => {
                const isBlock = className?.includes('language-')
                if (isBlock) {
                  return (
                    <pre className="bg-muted p-4 rounded-lg overflow-x-auto my-4">
                      <code className="text-sm font-mono">{children}</code>
                    </pre>
                  )
                }
                return <code className="font-mono text-sm bg-muted px-1.5 py-0.5 rounded">{children}</code>
              },
              ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-1">{children}</ol>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-primary/50 pl-4 italic text-muted-foreground my-4">
                  {children}
                </blockquote>
              ),
              h1: ({ children }) => <h1 className="text-2xl font-display font-semibold mt-6 mb-3">{children}</h1>,
              h2: ({ children }) => <h2 className="text-xl font-display font-semibold mt-5 mb-2">{children}</h2>,
              h3: ({ children }) => <h3 className="text-lg font-display font-semibold mt-4 mb-2">{children}</h3>,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Sources */}
        {sources && sources.length > 0 && (
          <div className="mt-4 pt-3 border-t border-border/50">
            <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
              <BookOpen className="w-3 h-3" />
              Sources used:
            </p>
            <div className="flex flex-wrap gap-2">
              {sources.map((source, index) => (
                <span
                  key={index}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs",
                    source.type === 'web' 
                      ? "bg-blue-500/10 text-blue-400"
                      : source.type === 'chapter'
                      ? "bg-green-500/10 text-green-400"
                      : "bg-primary/10 text-primary"
                  )}
                >
                  {source.type === 'web' ? (
                    <Globe className="w-3 h-3" />
                  ) : (
                    <BookOpen className="w-3 h-3" />
                  )}
                  {source.title || source.type}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

