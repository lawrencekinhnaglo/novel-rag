import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, MessageSquare, Trash2, MoreVertical } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { cn, formatDate, truncate } from '@/lib/utils'

export function ChatSidebar() {
  const { 
    sessions, 
    currentSessionId, 
    loadSessions, 
    createSession, 
    selectSession, 
    deleteSession 
  } = useChatStore()

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  return (
    <div className="w-72 h-full flex flex-col border-r border-border/50 bg-card/50">
      {/* Header */}
      <div className="p-4 border-b border-border/50">
        <button
          onClick={() => createSession()}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="font-medium">New Chat</span>
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto py-2">
        <AnimatePresence>
          {sessions.length === 0 ? (
            <div className="px-4 py-8 text-center text-muted-foreground">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No conversations yet</p>
              <p className="text-xs mt-1">Start a new chat to begin</p>
            </div>
          ) : (
            sessions.map((session) => (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="px-2"
              >
                <button
                  onClick={() => selectSession(session.id)}
                  className={cn(
                    "w-full group flex items-start gap-3 p-3 rounded-lg text-left transition-all",
                    "hover:bg-muted/50",
                    currentSessionId === session.id && "bg-muted"
                  )}
                >
                  <MessageSquare className={cn(
                    "w-4 h-4 mt-0.5 flex-shrink-0",
                    currentSessionId === session.id ? "text-primary" : "text-muted-foreground"
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      "font-medium text-sm truncate",
                      currentSessionId === session.id ? "text-primary" : "text-foreground"
                    )}>
                      {truncate(session.title, 30)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {session.message_count} messages • {formatDate(session.updated_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteSession(session.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-destructive/20 rounded transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-destructive" />
                  </button>
                </button>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

