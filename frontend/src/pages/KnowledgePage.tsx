import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Database, MessageSquare, FileText, Trash2, Search, X } from 'lucide-react'
import { knowledgeApi, searchApi, type Knowledge, type SearchResponse } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

export function KnowledgePage() {
  const [knowledge, setKnowledge] = useState<Knowledge[]>([])
  const [filter, setFilter] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [formData, setFormData] = useState({ source_type: 'document', title: '', content: '', tags: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadKnowledge()
  }, [filter])

  const loadKnowledge = async () => {
    setLoading(true)
    try {
      const data = await knowledgeApi.list(filter || undefined)
      setKnowledge(data)
    } catch (error) {
      console.error('Failed to load knowledge:', error)
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setIsSearching(true)
    try {
      const results = await searchApi.search(searchQuery, ['knowledge', 'chapters', 'ideas'], true)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    }
    setIsSearching(false)
  }

  const handleCreate = async () => {
    try {
      await knowledgeApi.create({
        source_type: formData.source_type,
        title: formData.title,
        content: formData.content,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
      })
      setIsCreating(false)
      setFormData({ source_type: 'document', title: '', content: '', tags: '' })
      loadKnowledge()
    } catch (error) {
      console.error('Failed to create:', error)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this?')) return
    try {
      await knowledgeApi.delete(id)
      loadKnowledge()
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'chat': return MessageSquare
      case 'document': return FileText
      default: return Database
    }
  }

  const getSourceColor = (type: string) => {
    switch (type) {
      case 'chat': return 'bg-blue-500/10 text-blue-400'
      case 'document': return 'bg-green-500/10 text-green-400'
      default: return 'bg-primary/10 text-primary'
    }
  }

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-semibold text-foreground">
            Knowledge Base
          </h1>
          <p className="text-muted-foreground">
            Your saved knowledge and RAG-searchable content
          </p>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="font-medium">Add Knowledge</span>
        </button>
      </div>

      {/* Search bar */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search across all content..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={isSearching}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </div>

      {/* Search Results */}
      <AnimatePresence>
        {searchResults && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6 p-4 rounded-xl bg-card border border-primary/30"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-foreground">
                Search Results ({searchResults.total_results})
              </h3>
              <button
                onClick={() => setSearchResults(null)}
                className="p-1 hover:bg-muted rounded"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {Object.entries(searchResults.results).map(([collection, items]) => (
                items.length > 0 && (
                  <div key={collection}>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                      {collection}
                    </p>
                    {(items as Array<Record<string, unknown>>).map((item, index) => (
                      <div key={index} className="p-2 rounded bg-muted/50 mb-1">
                        <p className="text-sm font-medium text-foreground">
                          {(item.title as string) || 'Untitled'}
                        </p>
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          {(item.content as string)?.slice(0, 100)}...
                        </p>
                      </div>
                    ))}
                  </div>
                )
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {[null, 'chat', 'document', 'idea'].map((type) => (
          <button
            key={type || 'all'}
            onClick={() => setFilter(type)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              filter === type
                ? "bg-primary/20 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            {type === null ? 'All' : type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {/* Create Form */}
      <AnimatePresence>
        {isCreating && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-6 p-4 rounded-xl bg-card border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-foreground">Add Knowledge</h3>
              <button
                onClick={() => setIsCreating(false)}
                className="p-1 hover:bg-muted rounded"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="flex gap-4">
                <select
                  value={formData.source_type}
                  onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="document">Document</option>
                  <option value="idea">Idea</option>
                </select>
                <input
                  type="text"
                  placeholder="Title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="flex-1 px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <textarea
                placeholder="Content..."
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                rows={6}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
              />
              <input
                type="text"
                placeholder="Tags (comma separated)"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
              <button
                onClick={handleCreate}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Save Knowledge
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Knowledge list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {knowledge.map((item) => {
              const Icon = getSourceIcon(item.source_type)
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-4 rounded-xl bg-card border border-border hover:border-primary/30 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className={cn("flex items-center gap-1.5 px-2 py-0.5 rounded text-xs", getSourceColor(item.source_type))}>
                      <Icon className="w-3 h-3" />
                      {item.source_type}
                    </div>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-1 hover:bg-destructive/20 rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-destructive" />
                    </button>
                  </div>
                  <h3 className="font-medium text-foreground mb-1">
                    {item.title || 'Untitled'}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                    {item.content}
                  </p>
                  {item.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {item.tags.map((tag) => (
                        <span key={tag} className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {formatDate(item.created_at)}
                  </p>
                </motion.div>
              )
            })}
            {knowledge.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No knowledge entries yet</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

