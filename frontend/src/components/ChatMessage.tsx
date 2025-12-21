import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { User, Bot, Sparkles, Globe, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message } from '@/lib/api'

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const sources = message.metadata?.sources as Array<{ type: string; title: string; url?: string }> | undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-4 p-4 rounded-xl",
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
        <div className="flex items-center gap-2 mb-2">
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

