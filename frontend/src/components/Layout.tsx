import { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  MessageSquare, 
  BookOpen, 
  Database, 
  Network, 
  Settings, 
  Menu,
  X,
  Feather
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { path: '/', label: 'Chat', icon: MessageSquare },
  { path: '/chapters', label: 'Chapters', icon: BookOpen },
  { path: '/knowledge', label: 'Knowledge', icon: Database },
  { path: '/graph', label: 'Story Graph', icon: Network },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()

  return (
    <div className="flex h-screen bg-gradient-novel overflow-hidden">
      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 280 : 72 }}
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
                <p className="text-xs text-muted-foreground">AI Writing Assistant</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto">
          <ul className="space-y-1 px-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path
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

        {/* Footer */}
        <div className="p-4 border-t border-border/50">
          <AnimatePresence>
            {sidebarOpen && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-xs text-muted-foreground text-center"
              >
                Powered by Local LLM
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

