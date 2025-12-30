import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { User, Bot, Sparkles, Globe, BookOpen, Save, Check, Copy, Loader2, Wand2, UserPlus, BookMarked, Lightbulb, Search, FileText, Brain, ThumbsUp, ThumbsDown, X, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { knowledgeApi, chaptersApi, storyApi, type Message, type Chapter, type Series } from '@/lib/api'
import { useChatStore } from '@/store/chatStore'

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
  userMessageId?: number  // ID of the preceding user message (for feedback pairing)
}

export function ChatMessage({ message, isStreaming, sessionId, userMessageId }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const sources = message.metadata?.sources as Array<{ type: string; title: string; url?: string }> | undefined
  const detectedIntent = message.metadata?.detected_intent as { type: string; confidence: number } | undefined
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [copied, setCopied] = useState(false)
  
  // Chapter saving state
  const [showChapterModal, setShowChapterModal] = useState(false)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [isLoadingChapters, setIsLoadingChapters] = useState(false)
  const [isSavingToChapter, setIsSavingToChapter] = useState(false)
  const [savedToChapter, setSavedToChapter] = useState(false)
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null)
  const [newChapterTitle, setNewChapterTitle] = useState('')
  const [createNewChapter, setCreateNewChapter] = useState(false)
  
  // Get feedback state from store
  const { feedbackMap, setFeedback } = useChatStore()
  const currentFeedback = feedbackMap[message.id]
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  
  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!sessionId || !userMessageId || isUser) return
    
    setFeedbackLoading(true)
    try {
      await setFeedback(userMessageId, message.id, type)
    } finally {
      setFeedbackLoading(false)
    }
  }

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
  
  const openChapterModal = async () => {
    setShowChapterModal(true)
    setIsLoadingChapters(true)
    try {
      const chapterList = await chaptersApi.list()
      setChapters(chapterList)
    } catch (error) {
      console.error('Failed to load chapters:', error)
    } finally {
      setIsLoadingChapters(false)
    }
  }
  
  const handleSaveToChapter = async () => {
    if (!selectedChapterId && !createNewChapter) return
    
    setIsSavingToChapter(true)
    try {
      if (createNewChapter && newChapterTitle) {
        // Create new chapter with the content
        await chaptersApi.create({
          title: newChapterTitle,
          content: message.content,
          chapter_number: chapters.length + 1,
        })
      } else if (selectedChapterId) {
        // Append to existing chapter
        await chaptersApi.appendContent(selectedChapterId, message.content)
      }
      setSavedToChapter(true)
      setShowChapterModal(false)
      setTimeout(() => setSavedToChapter(false), 3000)
    } catch (error) {
      console.error('Failed to save to chapter:', error)
      alert('Failed to save to chapter')
    } finally {
      setIsSavingToChapter(false)
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
            <div className="flex items-center gap-1">
              {/* Like/Dislike buttons - always visible for better UX, only if we have valid DB IDs */}
              {userMessageId && userMessageId > 0 && message.id > 0 && sessionId && (
                <>
                  <button
                    onClick={() => handleFeedback('like')}
                    disabled={feedbackLoading}
                    className={cn(
                      "p-1.5 rounded-md transition-colors",
                      currentFeedback === 'like'
                        ? "bg-green-500/20 text-green-500"
                        : "hover:bg-muted text-muted-foreground hover:text-foreground"
                    )}
                    title="Like this response (will be used as context for future messages)"
                  >
                    <ThumbsUp className={cn("w-4 h-4", currentFeedback === 'like' && "fill-current")} />
                  </button>
                  <button
                    onClick={() => handleFeedback('dislike')}
                    disabled={feedbackLoading}
                    className={cn(
                      "p-1.5 rounded-md transition-colors",
                      currentFeedback === 'dislike'
                        ? "bg-red-500/20 text-red-500"
                        : "hover:bg-muted text-muted-foreground hover:text-foreground"
                    )}
                    title="Dislike this response (will be removed from context)"
                  >
                    <ThumbsDown className={cn("w-4 h-4", currentFeedback === 'dislike' && "fill-current")} />
                  </button>
                  <div className="w-px h-4 bg-border mx-1" />
                </>
              )}
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
                  <Brain className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={openChapterModal}
                disabled={savedToChapter}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  savedToChapter 
                    ? "text-green-500" 
                    : "hover:bg-muted text-muted-foreground hover:text-foreground"
                )}
                title="Save to Chapter"
              >
                {savedToChapter ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <FileText className="w-4 h-4" />
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
      
      {/* Save to Chapter Modal */}
      <AnimatePresence>
        {showChapterModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowChapterModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-card p-6 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[80vh] overflow-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <FileText className="w-5 h-5 text-primary" />
                  Save to Chapter
                </h2>
                <button
                  onClick={() => setShowChapterModal(false)}
                  className="p-1 rounded hover:bg-muted"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              {isLoadingChapters ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Create New Chapter Option */}
                  <button
                    onClick={() => {
                      setCreateNewChapter(true)
                      setSelectedChapterId(null)
                    }}
                    className={cn(
                      "w-full p-3 rounded-lg border text-left transition-colors flex items-center gap-2",
                      createNewChapter
                        ? "border-primary bg-primary/10"
                        : "border-border/50 hover:border-primary/30"
                    )}
                  >
                    <Plus className="w-4 h-4 text-primary" />
                    <span>Create New Chapter</span>
                  </button>
                  
                  {createNewChapter && (
                    <div className="pl-4">
                      <input
                        type="text"
                        placeholder="Chapter title..."
                        value={newChapterTitle}
                        onChange={(e) => setNewChapterTitle(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm"
                        autoFocus
                      />
                    </div>
                  )}
                  
                  {chapters.length > 0 && (
                    <>
                      <div className="text-sm text-muted-foreground">
                        Or append to existing chapter:
                      </div>
                      <div className="space-y-2 max-h-48 overflow-auto">
                        {chapters.map(chapter => (
                          <button
                            key={chapter.id}
                            onClick={() => {
                              setSelectedChapterId(chapter.id)
                              setCreateNewChapter(false)
                            }}
                            className={cn(
                              "w-full p-3 rounded-lg border text-left transition-colors",
                              selectedChapterId === chapter.id
                                ? "border-primary bg-primary/10"
                                : "border-border/50 hover:border-primary/30"
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-sm">{chapter.title}</span>
                              <span className="text-xs text-muted-foreground">
                                Ch. {chapter.chapter_number}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                              {chapter.word_count} words
                            </p>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  
                  {/* Preview */}
                  <div className="p-3 rounded-lg bg-muted/50 border border-border/30">
                    <p className="text-xs text-muted-foreground mb-1">Content preview:</p>
                    <p className="text-sm line-clamp-3">{message.content.slice(0, 200)}...</p>
                  </div>
                  
                  {/* Action buttons */}
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setShowChapterModal(false)}
                      className="px-4 py-2 rounded-lg border border-border text-sm"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveToChapter}
                      disabled={isSavingToChapter || (!selectedChapterId && (!createNewChapter || !newChapterTitle))}
                      className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm disabled:opacity-50 flex items-center gap-2"
                    >
                      {isSavingToChapter ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      {createNewChapter ? 'Create & Save' : 'Append to Chapter'}
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

