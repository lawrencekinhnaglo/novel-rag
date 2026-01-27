import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  X, Save, Maximize2, Minimize2, Clock, Target, 
  Loader2, Check, Sparkles, ChevronLeft, ChevronRight,
  Sun, Moon, Type, AlignLeft, AlignCenter, Settings,
  FileText, Wand2, Zap, Eye, EyeOff, PanelLeftClose, PanelLeft
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { chaptersApi, type Chapter } from '@/lib/api'

interface WritingStats {
  wordCount: number
  charCount: number
  sessionWords: number
  startTime: Date
  lastSaved: Date | null
}

type Theme = 'dark' | 'sepia' | 'light'

export function WritingModePage() {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null)
  const [content, setContent] = useState('')
  const [title, setTitle] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [showAIPanel, setShowAIPanel] = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState('')
  const [isAILoading, setIsAILoading] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'unsaved' | 'saving'>('saved')
  
  // Writing settings
  const [theme, setTheme] = useState<Theme>('dark')
  const [fontSize, setFontSize] = useState(18)
  const [lineHeight, setLineHeight] = useState(1.8)
  const [maxWidth, setMaxWidth] = useState(720)
  const [wordGoal, setWordGoal] = useState(1000)
  const [focusMode, setFocusMode] = useState(false)
  
  // Stats
  const [stats, setStats] = useState<WritingStats>({
    wordCount: 0,
    charCount: 0,
    sessionWords: 0,
    startTime: new Date(),
    lastSaved: null
  })
  
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const initialWordCountRef = useRef(0)

  useEffect(() => {
    loadChapters()
    
    // Check for fullscreen preference
    const savedFullscreen = localStorage.getItem('writing-fullscreen')
    if (savedFullscreen === 'true') {
      setIsFullscreen(true)
    }
    
    // Load settings
    const savedSettings = localStorage.getItem('writing-settings')
    if (savedSettings) {
      const settings = JSON.parse(savedSettings)
      setTheme(settings.theme || 'dark')
      setFontSize(settings.fontSize || 18)
      setLineHeight(settings.lineHeight || 1.8)
      setMaxWidth(settings.maxWidth || 720)
      setWordGoal(settings.wordGoal || 1000)
    }
    
    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    // Save settings
    localStorage.setItem('writing-settings', JSON.stringify({
      theme, fontSize, lineHeight, maxWidth, wordGoal
    }))
  }, [theme, fontSize, lineHeight, maxWidth, wordGoal])

  useEffect(() => {
    // Update stats when content changes
    const words = content.trim().split(/\s+/).filter(w => w.length > 0).length
    const chars = content.length
    
    setStats(prev => ({
      ...prev,
      wordCount: words,
      charCount: chars,
      sessionWords: words - initialWordCountRef.current
    }))
    
    // Mark as unsaved
    if (selectedChapterId && saveStatus === 'saved') {
      setSaveStatus('unsaved')
    }
    
    // Auto-save after 5 seconds of no typing
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    
    if (selectedChapterId && content) {
      autoSaveTimeoutRef.current = setTimeout(() => {
        handleSave(true)
      }, 5000)
    }
  }, [content])

  const loadChapters = async () => {
    try {
      const data = await chaptersApi.list()
      setChapters(data.sort((a, b) => (a.chapter_number || 0) - (b.chapter_number || 0)))
    } catch (error) {
      console.error('Failed to load chapters:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadChapter = async (id: number) => {
    try {
      const chapter = await chaptersApi.get(id)
      setContent(chapter.content || '')
      setTitle(chapter.title || '')
      initialWordCountRef.current = (chapter.content || '').trim().split(/\s+/).filter(w => w.length > 0).length
      setSaveStatus('saved')
      
      // Focus textarea
      setTimeout(() => {
        textareaRef.current?.focus()
      }, 100)
    } catch (error) {
      console.error('Failed to load chapter:', error)
    }
  }

  const handleSelectChapter = (id: number) => {
    setSelectedChapterId(id)
    loadChapter(id)
    setStats(prev => ({ ...prev, startTime: new Date(), sessionWords: 0 }))
  }

  const handleSave = async (isAutoSave = false) => {
    if (!selectedChapterId || !content) return
    
    setSaveStatus('saving')
    setIsSaving(true)
    
    try {
      await chaptersApi.update(selectedChapterId, {
        content,
        title,
        word_count: stats.wordCount
      })
      
      setSaveStatus('saved')
      setStats(prev => ({ ...prev, lastSaved: new Date() }))
    } catch (error) {
      console.error('Failed to save:', error)
      setSaveStatus('unsaved')
    } finally {
      setIsSaving(false)
    }
  }

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Cmd/Ctrl + S to save
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
    }
    
    // Cmd/Ctrl + Enter to toggle fullscreen
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      setIsFullscreen(f => !f)
    }
    
    // Escape to exit fullscreen
    if (e.key === 'Escape' && isFullscreen) {
      setIsFullscreen(false)
    }
  }, [isFullscreen])

  const getAISuggestion = async () => {
    if (!content) return
    
    setIsAILoading(true)
    setShowAIPanel(true)
    
    try {
      // Get the last few sentences for context
      const lastParagraph = content.split('\n\n').pop() || content.slice(-500)
      
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `Continue this text naturally with 2-3 sentences. Only provide the continuation, no explanation:\n\n${lastParagraph}`,
          language: 'zh-TW'
        })
      })
      
      const data = await response.json()
      setAiSuggestion(data.response || '')
    } catch (error) {
      console.error('AI suggestion failed:', error)
      setAiSuggestion('Failed to get suggestion')
    } finally {
      setIsAILoading(false)
    }
  }

  const acceptAISuggestion = () => {
    if (aiSuggestion) {
      setContent(prev => prev + ' ' + aiSuggestion)
      setAiSuggestion('')
      setShowAIPanel(false)
      textareaRef.current?.focus()
    }
  }

  const themeStyles: Record<Theme, { bg: string; text: string; accent: string }> = {
    dark: { bg: 'bg-[#1a1a2e]', text: 'text-gray-200', accent: 'text-purple-400' },
    sepia: { bg: 'bg-[#f4ecd8]', text: 'text-[#5c4b37]', accent: 'text-amber-700' },
    light: { bg: 'bg-white', text: 'text-gray-800', accent: 'text-blue-600' }
  }

  const currentTheme = themeStyles[theme]
  const progressPercent = Math.min((stats.wordCount / wordGoal) * 100, 100)
  const sessionMinutes = Math.floor((Date.now() - stats.startTime.getTime()) / 60000)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div 
      className={cn(
        "h-screen flex transition-colors duration-300",
        currentTheme.bg,
        isFullscreen && "fixed inset-0 z-50"
      )}
      onKeyDown={handleKeyDown}
    >
      {/* Sidebar */}
      <AnimatePresence>
        {showSidebar && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="h-full border-r border-border/30 bg-black/20 backdrop-blur-sm overflow-hidden flex flex-col"
          >
            <div className="p-4 border-b border-border/30">
              <h2 className={cn("font-semibold", currentTheme.text)}>Chapters</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {chapters.map(chapter => (
                <button
                  key={chapter.id}
                  onClick={() => handleSelectChapter(chapter.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg mb-1 transition-colors",
                    selectedChapterId === chapter.id
                      ? "bg-primary/20 text-primary"
                      : "hover:bg-white/10 text-gray-400"
                  )}
                >
                  <div className="font-medium truncate">{chapter.title}</div>
                  <div className="text-xs opacity-60">
                    Ch. {chapter.chapter_number} • {chapter.word_count?.toLocaleString()} words
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Writing Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border/20">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(s => !s)}
              className={cn("p-2 rounded-lg hover:bg-white/10 transition-colors", currentTheme.text)}
            >
              {showSidebar ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
            </button>
            
            {selectedChapterId && (
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className={cn(
                  "bg-transparent border-none text-lg font-medium focus:outline-none",
                  currentTheme.text
                )}
                placeholder="Chapter Title"
              />
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* Save Status */}
            <div className={cn("flex items-center gap-1 px-2 py-1 rounded text-sm", currentTheme.text)}>
              {saveStatus === 'saving' && <Loader2 className="w-4 h-4 animate-spin" />}
              {saveStatus === 'saved' && <Check className="w-4 h-4 text-green-400" />}
              {saveStatus === 'unsaved' && <span className="text-yellow-400">•</span>}
              <span className="text-xs opacity-60">
                {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Unsaved'}
              </span>
            </div>
            
            {/* AI Assist */}
            <button
              onClick={getAISuggestion}
              disabled={isAILoading || !content}
              className={cn(
                "p-2 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-50",
                currentTheme.accent
              )}
              title="Get AI Suggestion"
            >
              <Wand2 className="w-5 h-5" />
            </button>
            
            {/* Settings */}
            <button
              onClick={() => setShowSettings(s => !s)}
              className={cn("p-2 rounded-lg hover:bg-white/10 transition-colors", currentTheme.text)}
            >
              <Settings className="w-5 h-5" />
            </button>
            
            {/* Fullscreen */}
            <button
              onClick={() => {
                setIsFullscreen(f => !f)
                localStorage.setItem('writing-fullscreen', (!isFullscreen).toString())
              }}
              className={cn("p-2 rounded-lg hover:bg-white/10 transition-colors", currentTheme.text)}
            >
              {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
            </button>
            
            {/* Save */}
            <button
              onClick={() => handleSave()}
              disabled={isSaving || saveStatus === 'saved'}
              className="flex items-center gap-2 px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              Save
            </button>
          </div>
        </div>

        {/* Writing Area */}
        <div className="flex-1 overflow-y-auto flex justify-center">
          {selectedChapterId ? (
            <div 
              className="w-full p-8"
              style={{ maxWidth: `${maxWidth}px` }}
            >
              <textarea
                ref={textareaRef}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className={cn(
                  "w-full h-full min-h-[70vh] bg-transparent border-none resize-none focus:outline-none",
                  currentTheme.text,
                  focusMode && "focus-mode"
                )}
                style={{
                  fontSize: `${fontSize}px`,
                  lineHeight: lineHeight
                }}
                placeholder="Start writing..."
              />
            </div>
          ) : (
            <div className={cn("flex flex-col items-center justify-center h-full", currentTheme.text)}>
              <FileText className="w-16 h-16 mb-4 opacity-30" />
              <p className="text-lg opacity-60">Select a chapter to start writing</p>
            </div>
          )}
        </div>

        {/* Bottom Stats Bar */}
        <div className={cn("px-4 py-2 border-t border-border/20 flex items-center justify-between text-sm", currentTheme.text)}>
          <div className="flex items-center gap-6 opacity-60">
            <span>{stats.wordCount.toLocaleString()} words</span>
            <span>{stats.charCount.toLocaleString()} characters</span>
            <span className={stats.sessionWords > 0 ? "text-green-400" : ""}>
              +{stats.sessionWords} this session
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {sessionMinutes}m
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Progress to goal */}
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 opacity-60" />
              <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className={cn(
                    "h-full transition-all duration-500",
                    progressPercent >= 100 ? "bg-green-500" : "bg-primary"
                  )}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <span className="text-xs opacity-60">{Math.round(progressPercent)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* AI Suggestion Panel */}
      <AnimatePresence>
        {showAIPanel && (
          <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 300, opacity: 0 }}
            className="w-80 border-l border-border/30 bg-black/30 backdrop-blur-sm p-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className={cn("font-semibold flex items-center gap-2", currentTheme.accent)}>
                <Sparkles className="w-4 h-4" />
                AI Suggestion
              </h3>
              <button
                onClick={() => setShowAIPanel(false)}
                className={cn("p-1 hover:bg-white/10 rounded", currentTheme.text)}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {isAILoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
              </div>
            ) : aiSuggestion ? (
              <div className="space-y-4">
                <div className={cn("p-3 bg-white/5 rounded-lg text-sm", currentTheme.text)}>
                  {aiSuggestion}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={acceptAISuggestion}
                    className="flex-1 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm font-medium"
                  >
                    Accept
                  </button>
                  <button
                    onClick={getAISuggestion}
                    className="flex-1 py-2 bg-white/10 hover:bg-white/20 text-gray-300 rounded-lg text-sm font-medium"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            ) : (
              <p className={cn("text-sm opacity-60", currentTheme.text)}>
                Click the wand icon to get AI suggestions based on your current text.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Settings Panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute top-14 right-4 w-72 bg-card border border-border rounded-xl shadow-xl p-4 z-50"
          >
            <h3 className="font-semibold mb-4">Writing Settings</h3>
            
            <div className="space-y-4">
              {/* Theme */}
              <div>
                <label className="text-sm text-muted-foreground block mb-2">Theme</label>
                <div className="flex gap-2">
                  {(['dark', 'sepia', 'light'] as Theme[]).map(t => (
                    <button
                      key={t}
                      onClick={() => setTheme(t)}
                      className={cn(
                        "flex-1 py-2 rounded-lg text-sm font-medium transition-colors capitalize",
                        theme === t
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted hover:bg-muted/80"
                      )}
                    >
                      {t === 'dark' && <Moon className="w-4 h-4 mx-auto" />}
                      {t === 'sepia' && <Sun className="w-4 h-4 mx-auto" />}
                      {t === 'light' && <Sun className="w-4 h-4 mx-auto" />}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Font Size */}
              <div>
                <label className="text-sm text-muted-foreground block mb-2">
                  Font Size: {fontSize}px
                </label>
                <input
                  type="range"
                  min="14"
                  max="24"
                  value={fontSize}
                  onChange={(e) => setFontSize(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              
              {/* Line Height */}
              <div>
                <label className="text-sm text-muted-foreground block mb-2">
                  Line Height: {lineHeight}
                </label>
                <input
                  type="range"
                  min="1.4"
                  max="2.4"
                  step="0.1"
                  value={lineHeight}
                  onChange={(e) => setLineHeight(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              
              {/* Max Width */}
              <div>
                <label className="text-sm text-muted-foreground block mb-2">
                  Max Width: {maxWidth}px
                </label>
                <input
                  type="range"
                  min="500"
                  max="1000"
                  step="20"
                  value={maxWidth}
                  onChange={(e) => setMaxWidth(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              
              {/* Word Goal */}
              <div>
                <label className="text-sm text-muted-foreground block mb-2">
                  Daily Word Goal: {wordGoal.toLocaleString()}
                </label>
                <input
                  type="range"
                  min="500"
                  max="5000"
                  step="100"
                  value={wordGoal}
                  onChange={(e) => setWordGoal(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
            
            <button
              onClick={() => setShowSettings(false)}
              className="w-full mt-4 py-2 bg-muted hover:bg-muted/80 rounded-lg text-sm font-medium"
            >
              Close
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
