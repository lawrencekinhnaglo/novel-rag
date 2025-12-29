import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Library,
  Sparkles,
  Plus,
  ChevronRight,
  Loader2,
  Lightbulb,
  Shield,
  Users,
  MessageSquare,
  FileText,
  Brain,
  BarChart3,
  Link2,
  ExternalLink,
  FolderOpen,
  BookMarked,
  Pencil,
  Network
} from 'lucide-react'
import { storyApi, knowledgeApi, sessionsApi, type Series } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/store/chatStore'

interface WorkspaceData {
  series: {
    id: number
    title: string
    premise?: string
    themes: string[]
    total_planned_books: number
    language: string
  }
  statistics: {
    total_books: number
    total_chapters: number
    total_words: number
    total_characters: number
    total_knowledge: number
    total_foreshadowing: number
    total_rules: number
    total_facts: number
  }
  books: Array<{
    id: number
    book_number: number
    title: string
    theme?: string
    status: string
    chapter_count: number
    total_words: number
    target_word_count?: number
  }>
  chapters: Array<{
    id: number
    book_id: number
    book_number: number
    book_title: string
    title: string
    chapter_number: number
    pov_character?: string
    word_count: number
    summary?: string
  }>
  characters: Array<{
    id: number
    name: string
    description?: string
    personality?: string
    verification_status: string
  }>
  knowledge: Array<{
    id: number
    title?: string
    source_type: string
    category: string
    content: string
    tags: string[]
  }>
  foreshadowing: Array<{
    id: number
    title: string
    status: string
    planted_book: number
    planted_chapter: number
    subtlety: number
  }>
  world_rules: Array<{
    id: number
    category: string
    name: string
    is_hard_rule: boolean
  }>
  chat_sessions: Array<{
    id: string
    title: string
    updated_at?: string
  }>
}

type WorkspaceTab = 'overview' | 'chapters' | 'characters' | 'knowledge' | 'chat' | 'analysis'

const API_BASE = '/api/v1'

async function fetchWorkspace(seriesId: number): Promise<WorkspaceData> {
  const response = await fetch(`${API_BASE}/story/workspace/${seriesId}`)
  if (!response.ok) throw new Error('Failed to fetch workspace')
  return response.json()
}

async function linkKnowledge(seriesId: number, knowledgeId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/story/workspace/${seriesId}/link-knowledge?knowledge_id=${knowledgeId}`, {
    method: 'POST'
  })
  if (!response.ok) throw new Error('Failed to link knowledge')
}

async function linkSession(seriesId: number, sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/story/workspace/${seriesId}/link-session?session_id=${sessionId}`, {
    method: 'POST'
  })
  if (!response.ok) throw new Error('Failed to link session')
}

export function StoryWorkspacePage() {
  const navigate = useNavigate()
  const [series, setSeries] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null)
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('overview')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Link dialogs
  const [showLinkKnowledge, setShowLinkKnowledge] = useState(false)
  const [showLinkChat, setShowLinkChat] = useState(false)
  const [availableKnowledge, setAvailableKnowledge] = useState<Array<{id: number, title: string}>>([])
  const [availableSessions, setAvailableSessions] = useState<Array<{id: string, title: string}>>([])
  
  const { selectSession, setProvider, setLanguage } = useChatStore()

  useEffect(() => {
    loadSeries()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadWorkspace(selectedSeriesId)
    }
  }, [selectedSeriesId])

  const loadSeries = async () => {
    try {
      const data = await storyApi.listSeries()
      setSeries(data)
      // Auto-select first series if available
      if (data.length > 0 && !selectedSeriesId) {
        setSelectedSeriesId(data[0].id)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const loadWorkspace = async (seriesId: number) => {
    try {
      setIsLoading(true)
      const data = await fetchWorkspace(seriesId)
      setWorkspace(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setIsLoading(false)
    }
  }

  const loadAvailableKnowledge = async () => {
    try {
      const data = await knowledgeApi.list()
      setAvailableKnowledge(data.map(k => ({ id: k.id, title: k.title || 'Untitled' })))
    } catch (e) {
      console.error('Failed to load knowledge:', e)
    }
  }

  const loadAvailableSessions = async () => {
    try {
      const { sessions } = await sessionsApi.list()
      setAvailableSessions(sessions.map(s => ({ id: s.id, title: s.title })))
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }

  const handleLinkKnowledge = async (knowledgeId: number) => {
    if (!selectedSeriesId) return
    try {
      await linkKnowledge(selectedSeriesId, knowledgeId)
      setShowLinkKnowledge(false)
      loadWorkspace(selectedSeriesId)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const handleLinkSession = async (sessionId: string) => {
    if (!selectedSeriesId) return
    try {
      await linkSession(selectedSeriesId, sessionId)
      setShowLinkChat(false)
      loadWorkspace(selectedSeriesId)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const startChatWithContext = async (sessionId?: string) => {
    if (sessionId) {
      await selectSession(sessionId)
    }
    // Set the language from series if available
    if (workspace?.series.language) {
      setLanguage(workspace.series.language as 'en' | 'zh-TW' | 'zh-CN')
    }
    navigate('/')
  }

  const tabs = [
    { id: 'overview' as WorkspaceTab, label: 'Overview', icon: BarChart3 },
    { id: 'chapters' as WorkspaceTab, label: 'Chapters', icon: FileText },
    { id: 'characters' as WorkspaceTab, label: 'Characters', icon: Users },
    { id: 'knowledge' as WorkspaceTab, label: 'Knowledge', icon: Brain },
    { id: 'chat' as WorkspaceTab, label: 'Chat Sessions', icon: MessageSquare },
    { id: 'analysis' as WorkspaceTab, label: 'Analysis', icon: Sparkles }
  ]

  return (
    <div className="h-full flex">
      {/* Series Sidebar */}
      <div className="w-72 border-r border-border/50 bg-card/30 flex flex-col">
        <div className="p-4 border-b border-border/50">
          <h2 className="text-lg font-display font-semibold flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-primary" />
            Story Workspaces
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Select a series to manage
          </p>
        </div>
        
        <div className="flex-1 overflow-auto p-2 space-y-1">
          {series.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedSeriesId(s.id)}
              className={cn(
                'w-full p-3 rounded-lg text-left transition-all',
                selectedSeriesId === s.id
                  ? 'bg-primary/10 border border-primary/30'
                  : 'hover:bg-accent/10 border border-transparent'
              )}
            >
              <div className="flex items-center gap-2">
                <Library className={cn(
                  'w-4 h-4',
                  selectedSeriesId === s.id ? 'text-primary' : 'text-muted-foreground'
                )} />
                <span className="font-medium text-sm truncate">{s.title}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 ml-6">
                {s.book_count || 0} / {s.total_planned_books} books
              </p>
            </button>
          ))}
        </div>
        
        <div className="p-3 border-t border-border/50">
          <button
            onClick={() => navigate('/story')}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-sm"
          >
            <Plus className="w-4 h-4" />
            New Series
          </button>
        </div>
      </div>

      {/* Main Workspace Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!workspace ? (
          <div className="flex-1 flex items-center justify-center">
            {isLoading ? (
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            ) : (
              <div className="text-center">
                <Library className="w-16 h-16 mx-auto text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-medium text-muted-foreground">Select a Series</h3>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  Choose a series from the sidebar to open its workspace
                </p>
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Workspace Header */}
            <div className="px-6 py-4 border-b border-border/50 bg-gradient-to-r from-primary/5 to-accent/5">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-display font-bold text-foreground">
                    {workspace.series.title}
                  </h1>
                  {workspace.series.premise && (
                    <p className="text-sm text-muted-foreground mt-1 max-w-xl line-clamp-1">
                      {workspace.series.premise}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {workspace.series.themes.slice(0, 3).map((theme, i) => (
                    <span key={i} className="px-2 py-1 rounded-full bg-accent/20 text-xs text-accent">
                      {theme}
                    </span>
                  ))}
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-1 mt-4">
                {tabs.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors text-sm',
                      activeTab === tab.id
                        ? 'bg-background shadow-sm text-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                    )}
                  >
                    <tab.icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-auto p-6">
              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: 'Books', value: workspace.statistics.total_books, icon: BookOpen, color: 'text-blue-500' },
                      { label: 'Chapters', value: workspace.statistics.total_chapters, icon: FileText, color: 'text-green-500' },
                      { label: 'Words', value: workspace.statistics.total_words.toLocaleString(), icon: Pencil, color: 'text-purple-500' },
                      { label: 'Characters', value: workspace.statistics.total_characters, icon: Users, color: 'text-orange-500' },
                      { label: 'Knowledge', value: workspace.statistics.total_knowledge, icon: Brain, color: 'text-cyan-500' },
                      { label: 'Foreshadowing', value: workspace.statistics.total_foreshadowing, icon: Lightbulb, color: 'text-yellow-500' },
                      { label: 'World Rules', value: workspace.statistics.total_rules, icon: Shield, color: 'text-red-500' },
                      { label: 'Story Facts', value: workspace.statistics.total_facts, icon: BookMarked, color: 'text-pink-500' }
                    ].map((stat, i) => (
                      <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="p-4 rounded-xl bg-card border border-border/50"
                      >
                        <div className="flex items-center gap-3">
                          <div className={cn('p-2 rounded-lg bg-background', stat.color)}>
                            <stat.icon className="w-5 h-5" />
                          </div>
                          <div>
                            <p className="text-2xl font-bold">{stat.value}</p>
                            <p className="text-xs text-muted-foreground">{stat.label}</p>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>

                  {/* Quick Actions */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <button
                      onClick={() => startChatWithContext()}
                      className="p-4 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20 hover:border-primary/40 transition-colors text-left"
                    >
                      <MessageSquare className="w-6 h-6 text-primary mb-2" />
                      <h3 className="font-medium">Chat with AI</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        Discuss your story with context-aware AI
                      </p>
                    </button>
                    
                    <button
                      onClick={() => navigate('/chapters')}
                      className="p-4 rounded-xl bg-gradient-to-br from-green-500/10 to-green-500/5 border border-green-500/20 hover:border-green-500/40 transition-colors text-left"
                    >
                      <FileText className="w-6 h-6 text-green-500 mb-2" />
                      <h3 className="font-medium">Write Chapter</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        Create a new chapter for this series
                      </p>
                    </button>
                    
                    <button
                      onClick={() => navigate('/graph')}
                      className="p-4 rounded-xl bg-gradient-to-br from-purple-500/10 to-purple-500/5 border border-purple-500/20 hover:border-purple-500/40 transition-colors text-left"
                    >
                      <Network className="w-6 h-6 text-purple-500 mb-2" />
                      <h3 className="font-medium">Story Graph</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        Visualize characters and relationships
                      </p>
                    </button>
                  </div>

                  {/* Books Overview */}
                  <div>
                    <h2 className="text-lg font-semibold mb-4">Books</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {workspace.books.map(book => (
                        <div
                          key={book.id}
                          className="p-4 rounded-xl bg-card border border-border/50 hover:border-primary/30 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="text-xs text-muted-foreground">Book {book.book_number}</span>
                              <h3 className="font-medium mt-0.5">{book.title}</h3>
                            </div>
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-xs',
                              book.status === 'published' ? 'bg-green-500/20 text-green-500' :
                              book.status === 'editing' ? 'bg-yellow-500/20 text-yellow-500' :
                              book.status === 'drafting' ? 'bg-blue-500/20 text-blue-500' :
                              'bg-muted text-muted-foreground'
                            )}>
                              {book.status}
                            </span>
                          </div>
                          {book.theme && (
                            <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{book.theme}</p>
                          )}
                          <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                            <span>{book.chapter_count} chapters</span>
                            <span>{book.total_words.toLocaleString()} words</span>
                          </div>
                          {book.target_word_count && (
                            <div className="mt-2">
                              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-primary rounded-full"
                                  style={{ width: `${Math.min(100, (book.total_words / book.target_word_count) * 100)}%` }}
                                />
                              </div>
                              <p className="text-xs text-muted-foreground mt-1 text-right">
                                {Math.round((book.total_words / book.target_word_count) * 100)}% of target
                              </p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Chapters Tab */}
              {activeTab === 'chapters' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">All Chapters</h2>
                    <button
                      onClick={() => navigate('/chapters')}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                    >
                      <Plus className="w-4 h-4" />
                      New Chapter
                    </button>
                  </div>
                  
                  {workspace.chapters.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No chapters yet. Start writing!</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {workspace.chapters.map(chapter => (
                        <div
                          key={chapter.id}
                          className="p-4 rounded-lg bg-card border border-border/50 hover:border-primary/30 transition-colors cursor-pointer"
                          onClick={() => navigate(`/chapters`)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <span className="px-2 py-0.5 rounded bg-accent/20 text-xs text-accent">
                                Book {chapter.book_number}
                              </span>
                              <span className="text-sm text-muted-foreground">
                                Chapter {chapter.chapter_number}
                              </span>
                              <h3 className="font-medium">{chapter.title}</h3>
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              {chapter.pov_character && (
                                <span className="flex items-center gap-1">
                                  <Users className="w-3 h-3" />
                                  {chapter.pov_character}
                                </span>
                              )}
                              <span>{chapter.word_count.toLocaleString()} words</span>
                              <ChevronRight className="w-4 h-4" />
                            </div>
                          </div>
                          {chapter.summary && (
                            <p className="text-sm text-muted-foreground mt-2 line-clamp-1">
                              {chapter.summary}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Characters Tab */}
              {activeTab === 'characters' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Characters</h2>
                    <button
                      onClick={() => navigate('/graph')}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                    >
                      <Plus className="w-4 h-4" />
                      Add Character
                    </button>
                  </div>
                  
                  {workspace.characters.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No characters yet. Create some in the Story Graph!</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {workspace.characters.map(char => (
                        <div
                          key={char.id}
                          className="p-4 rounded-xl bg-card border border-border/50"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
                              <span className="text-lg font-bold text-primary">{char.name[0]}</span>
                            </div>
                            <div>
                              <h3 className="font-medium">{char.name}</h3>
                              {char.verification_status === 'pending' && (
                                <span className="text-xs text-yellow-500">Pending verification</span>
                              )}
                            </div>
                          </div>
                          {char.description && (
                            <p className="text-sm text-muted-foreground mt-3 line-clamp-2">
                              {char.description}
                            </p>
                          )}
                          {char.personality && (
                            <p className="text-xs text-accent mt-2 line-clamp-1">
                              {char.personality}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Knowledge Tab */}
              {activeTab === 'knowledge' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Linked Knowledge</h2>
                    <button
                      onClick={() => {
                        loadAvailableKnowledge()
                        setShowLinkKnowledge(true)
                      }}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                    >
                      <Link2 className="w-4 h-4" />
                      Link Knowledge
                    </button>
                  </div>
                  
                  {workspace.knowledge.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <Brain className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No knowledge linked yet. Link existing knowledge or create new!</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {workspace.knowledge.map(k => (
                        <div
                          key={k.id}
                          className="p-4 rounded-lg bg-card border border-border/50"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded bg-accent/20 text-xs text-accent">
                                  {k.category}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {k.source_type}
                                </span>
                              </div>
                              <h3 className="font-medium mt-1">{k.title || 'Untitled'}</h3>
                            </div>
                            <button
                              onClick={() => navigate('/knowledge')}
                              className="p-1 hover:bg-accent/20 rounded"
                            >
                              <ExternalLink className="w-4 h-4 text-muted-foreground" />
                            </button>
                          </div>
                          <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                            {k.content}
                          </p>
                          {k.tags.length > 0 && (
                            <div className="flex gap-1 mt-2 flex-wrap">
                              {k.tags.slice(0, 5).map((tag, i) => (
                                <span key={i} className="px-2 py-0.5 rounded bg-muted text-xs">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Chat Sessions Tab */}
              {activeTab === 'chat' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Chat Sessions</h2>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          loadAvailableSessions()
                          setShowLinkChat(true)
                        }}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent/20 text-accent text-sm"
                      >
                        <Link2 className="w-4 h-4" />
                        Link Session
                      </button>
                      <button
                        onClick={() => startChatWithContext()}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                      >
                        <Plus className="w-4 h-4" />
                        New Chat
                      </button>
                    </div>
                  </div>
                  
                  {workspace.chat_sessions.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No chat sessions linked. Start a new conversation!</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {workspace.chat_sessions.map(session => (
                        <button
                          key={session.id}
                          onClick={() => startChatWithContext(session.id)}
                          className="w-full p-4 rounded-lg bg-card border border-border/50 hover:border-primary/30 transition-colors text-left"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <MessageSquare className="w-5 h-5 text-primary" />
                              <h3 className="font-medium truncate max-w-md">{session.title}</h3>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              {session.updated_at && (
                                <span>{new Date(session.updated_at).toLocaleDateString()}</span>
                              )}
                              <ChevronRight className="w-4 h-4" />
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Analysis Tab */}
              {activeTab === 'analysis' && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold">Story Analysis</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Use AI to analyze consistency, foreshadowing, and character knowledge
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Foreshadowing Summary */}
                    <div className="p-4 rounded-xl bg-card border border-border/50">
                      <div className="flex items-center gap-2 mb-4">
                        <Lightbulb className="w-5 h-5 text-yellow-500" />
                        <h3 className="font-medium">Foreshadowing Seeds</h3>
                      </div>
                      {workspace.foreshadowing.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No foreshadowing planted yet</p>
                      ) : (
                        <div className="space-y-2">
                          {workspace.foreshadowing.slice(0, 5).map(f => (
                            <div key={f.id} className="flex items-center justify-between text-sm">
                              <span className="truncate">{f.title}</span>
                              <span className={cn(
                                'px-2 py-0.5 rounded-full text-xs',
                                f.status === 'paid_off' ? 'bg-green-500/20 text-green-500' : 'bg-primary/20 text-primary'
                              )}>
                                {f.status}
                              </span>
                            </div>
                          ))}
                          <button
                            onClick={() => navigate('/story')}
                            className="text-sm text-primary hover:underline mt-2"
                          >
                            View all →
                          </button>
                        </div>
                      )}
                    </div>

                    {/* World Rules Summary */}
                    <div className="p-4 rounded-xl bg-card border border-border/50">
                      <div className="flex items-center gap-2 mb-4">
                        <Shield className="w-5 h-5 text-red-500" />
                        <h3 className="font-medium">World Rules</h3>
                      </div>
                      {workspace.world_rules.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No rules defined yet</p>
                      ) : (
                        <div className="space-y-2">
                          {workspace.world_rules.slice(0, 5).map(r => (
                            <div key={r.id} className="flex items-center justify-between text-sm">
                              <span className="truncate">{r.name}</span>
                              {r.is_hard_rule && (
                                <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-500">
                                  HARD
                                </span>
                              )}
                            </div>
                          ))}
                          <button
                            onClick={() => navigate('/story')}
                            className="text-sm text-primary hover:underline mt-2"
                          >
                            View all →
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => navigate('/story')}
                    className="w-full p-4 rounded-xl bg-gradient-to-r from-primary/10 to-accent/10 border border-primary/20 hover:border-primary/40 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <Sparkles className="w-6 h-6 text-primary" />
                      <div>
                        <h3 className="font-medium">Open Full Analysis Tools</h3>
                        <p className="text-sm text-muted-foreground">
                          Access consistency checks, character knowledge queries, and more
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-muted-foreground ml-auto" />
                    </div>
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Link Knowledge Modal */}
      <AnimatePresence>
        {showLinkKnowledge && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowLinkKnowledge(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-card p-6 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-96 overflow-auto"
              onClick={e => e.stopPropagation()}
            >
              <h2 className="text-xl font-semibold mb-4">Link Knowledge to Series</h2>
              <div className="space-y-2">
                {availableKnowledge.map(k => (
                  <button
                    key={k.id}
                    onClick={() => handleLinkKnowledge(k.id)}
                    className="w-full p-3 rounded-lg border border-border/50 hover:border-primary/30 text-left"
                  >
                    {k.title}
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Link Chat Modal */}
      <AnimatePresence>
        {showLinkChat && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowLinkChat(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-card p-6 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-96 overflow-auto"
              onClick={e => e.stopPropagation()}
            >
              <h2 className="text-xl font-semibold mb-4">Link Chat Session to Series</h2>
              <div className="space-y-2">
                {availableSessions.map(s => (
                  <button
                    key={s.id}
                    onClick={() => handleLinkSession(s.id)}
                    className="w-full p-3 rounded-lg border border-border/50 hover:border-primary/30 text-left truncate"
                  >
                    {s.title}
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

