import { useState, useEffect } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  MessageSquare, 
  BookOpen, 
  Database, 
  Network, 
  Settings, 
  Menu,
  X,
  Feather,
  Upload,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Globe,
  PenTool,
  ClipboardCheck,
  HelpCircle,
  Sparkles,
  Calendar,
  GitBranch,
  Download,
  Library
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { StoryTree } from './StoryTree'
import { QuickStartGuide, useQuickStart } from './QuickStartGuide'
import type { Series, Book } from '@/lib/api'

// Main 4-mode navigation (simplified)
const mainModes = [
  { path: '/', label: 'Chat', labelCn: '對話', icon: MessageSquare, description: 'Brainstorm with AI' },
  { path: '/knowledge', label: 'World', labelCn: '世界', icon: Globe, description: 'Build your universe' },
  { path: '/chapters', label: 'Write', labelCn: '寫作', icon: PenTool, description: 'Create chapters' },
  { path: '/verification', label: 'Review', labelCn: '審核', icon: ClipboardCheck, description: 'Verify & export' },
]

// Additional tools (collapsible)
const additionalTools = [
  { path: '/cowriter', label: 'Co-Writer ✨', icon: Feather, highlight: true },
  { path: '/workspace', label: 'Story Workspace', icon: Library },
  { path: '/story', label: 'Story Details', icon: BookOpen },
  { path: '/graph', label: 'Story Graph', icon: Network },
  { path: '/upload', label: 'Upload', icon: Upload },
  { path: '/plot-lab', label: 'Plot Lab', icon: Sparkles },
  { path: '/timeline', label: 'Timeline', icon: Calendar },
  { path: '/branches', label: 'Branches', icon: GitBranch },
  { path: '/export', label: 'Export', icon: Download },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showStoryTree, setShowStoryTree] = useState(true)
  const [showMoreTools, setShowMoreTools] = useState(false)
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | undefined>()
  const [selectedBookId, setSelectedBookId] = useState<number | undefined>()
  const location = useLocation()
  const navigate = useNavigate()
  const { showGuide, closeGuide } = useQuickStart()

  // Determine current main mode
  const currentMode = mainModes.find(m => 
    m.path === '/' ? location.pathname === '/' : location.pathname.startsWith(m.path)
  ) || mainModes[0]

  const handleSelectSeries = (series: Series) => {
    setSelectedSeriesId(series.id)
    // Navigate to workspace with this series
    navigate(`/workspace?series=${series.id}`)
  }

  const handleSelectBook = (book: Book, series: Series) => {
    setSelectedSeriesId(series.id)
    setSelectedBookId(book.id)
    navigate(`/chapters?book=${book.id}`)
  }

  const handleSelectChapter = (chapter: { id: number }, book: Book, series: Series) => {
    setSelectedSeriesId(series.id)
    setSelectedBookId(book.id)
    navigate(`/chapters?book=${book.id}&chapter=${chapter.id}`)
  }

  return (
    <div className="flex h-screen bg-gradient-novel overflow-hidden">
      {/* Quick Start Guide for first-time users */}
      {showGuide && (
        <QuickStartGuide 
          onClose={closeGuide} 
          language="zh-TW" 
        />
      )}

      {/* Left Sidebar - Story Tree */}
      <AnimatePresence>
        {showStoryTree && sidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 240, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="border-r border-border/50 bg-card/50 backdrop-blur-sm flex flex-col overflow-hidden"
          >
            {/* Story Tree Header */}
            <div className="flex items-center justify-between p-3 border-b border-border/50">
              <span className="text-sm font-medium text-foreground">Stories</span>
              <button 
                onClick={() => setShowStoryTree(false)}
                className="p-1 hover:bg-muted rounded"
              >
                <ChevronLeft className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            
            {/* Story Tree Content */}
            <div className="flex-1 overflow-y-auto">
              <StoryTree 
                selectedSeriesId={selectedSeriesId}
                selectedBookId={selectedBookId}
                onSelectSeries={handleSelectSeries}
                onSelectBook={handleSelectBook}
                onSelectChapter={handleSelectChapter}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Collapsed Story Tree Toggle */}
      {!showStoryTree && sidebarOpen && (
        <button
          onClick={() => setShowStoryTree(true)}
          className="w-8 border-r border-border/50 bg-card/50 flex items-center justify-center hover:bg-muted"
          title="Show Stories"
        >
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        </button>
      )}

      {/* Main Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 200 : 72 }}
        className="relative flex flex-col border-r border-border/50 glass"
      >
        {/* Logo */}
        <div className="flex items-center gap-3 p-4 border-b border-border/50">
          <motion.div
            whileHover={{ rotate: 15 }}
            className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/20"
          >
            <Feather className="w-5 h-5 text-primary" />
          </motion.div>
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
              >
                <h1 className="text-lg font-display font-semibold text-foreground">
                  Novel RAG
                </h1>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Main 4-Mode Navigation */}
        <nav className="py-4">
          <AnimatePresence>
            {sidebarOpen && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="px-4 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >
                Main
              </motion.p>
            )}
          </AnimatePresence>
          <ul className="space-y-1 px-2">
            {mainModes.map((item) => {
              const isActive = item.path === '/' 
                ? location.pathname === '/' 
                : location.pathname.startsWith(item.path)
              const Icon = item.icon
              
              return (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200",
                      "hover:bg-primary/10 hover-glow",
                      isActive && "bg-primary/15 text-primary"
                    )}
                    title={item.description}
                  >
                    <Icon className={cn(
                      "w-5 h-5 flex-shrink-0",
                      isActive ? "text-primary" : "text-muted-foreground"
                    )} />
                    <AnimatePresence>
                      {sidebarOpen && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className={cn(
                            "font-medium",
                            isActive ? "text-primary" : "text-foreground"
                          )}
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {isActive && (
                      <motion.div
                        layoutId="activeIndicator"
                        className="absolute left-0 w-1 h-8 bg-primary rounded-r-full"
                      />
                    )}
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* More Tools (Collapsible) */}
        <div className="flex-1 overflow-y-auto">
          <button
            onClick={() => setShowMoreTools(!showMoreTools)}
            className={cn(
              "w-full flex items-center gap-3 px-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:bg-muted/50",
              sidebarOpen ? "" : "justify-center"
            )}
          >
            {sidebarOpen ? (
              <>
                <span>More Tools</span>
                <ChevronRight className={cn(
                  "w-3 h-3 transition-transform",
                  showMoreTools && "rotate-90"
                )} />
              </>
            ) : (
              <Menu className="w-4 h-4" />
            )}
          </button>

          <AnimatePresence>
            {showMoreTools && (
              <motion.ul
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="space-y-1 px-2 overflow-hidden"
              >
                {additionalTools.map((item) => {
                  const isActive = location.pathname === item.path
                  const Icon = item.icon
                  
                  return (
                    <li key={item.path}>
                      <NavLink
                        to={item.path}
                        className={cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 text-sm",
                          "hover:bg-primary/10",
                          isActive && "bg-primary/15 text-primary"
                        )}
                      >
                        <Icon className={cn(
                          "w-4 h-4 flex-shrink-0",
                          isActive ? "text-primary" : "text-muted-foreground"
                        )} />
                        <AnimatePresence>
                          {sidebarOpen && (
                            <motion.span
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                              className={cn(
                                isActive ? "text-primary" : "text-foreground"
                              )}
                            >
                              {item.label}
                            </motion.span>
                          )}
                        </AnimatePresence>
                      </NavLink>
                    </li>
                  )
                })}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>

        {/* Toggle button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute -right-3 top-20 w-6 h-6 flex items-center justify-center rounded-full bg-card border border-border hover:bg-muted transition-colors"
        >
          {sidebarOpen ? (
            <X className="w-3 h-3 text-muted-foreground" />
          ) : (
            <Menu className="w-3 h-3 text-muted-foreground" />
          )}
        </button>

        {/* Footer with Help */}
        <div className="p-4 border-t border-border/50">
          <button
            onClick={() => {
              localStorage.removeItem('novel-rag-quickstart-seen')
              window.location.reload()
            }}
            className={cn(
              "flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors",
              sidebarOpen ? "" : "justify-center"
            )}
            title="Show Quick Start Guide"
          >
            <HelpCircle className="w-4 h-4" />
            {sidebarOpen && <span>Help</span>}
          </button>
        </div>
      </motion.aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {/* Mode description bar */}
        <div className="px-4 py-2 bg-card/30 border-b border-border/30 flex items-center gap-2">
          <currentMode.icon className="w-4 h-4 text-primary" />
          <span className="text-sm text-muted-foreground">{currentMode.description}</span>
        </div>
        
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
