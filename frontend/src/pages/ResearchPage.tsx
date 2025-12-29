import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Library, Plus, Trash2, ExternalLink, Search, Tag, 
  Loader2, Check, BookOpen, Link, Filter
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { researchApi, type ResearchItem } from '@/lib/api'

export function ResearchPage() {
  const [items, setItems] = useState<ResearchItem[]>([])
  const [categories, setCategories] = useState<Array<{ name: string; count: number }>>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [isAddingItem, setIsAddingItem] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{ id: number; title: string; summary?: string; similarity: number }> | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null)
  
  // Form state
  const [formData, setFormData] = useState({
    title: '',
    source_url: '',
    source_type: 'web',
    content: '',
    category: '',
    tags: ''
  })

  useEffect(() => {
    loadData()
  }, [selectedCategory])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [itemsData, categoriesData] = await Promise.all([
        researchApi.list(undefined, selectedCategory || undefined),
        researchApi.getCategories()
      ])
      setItems(itemsData)
      setCategories(categoriesData)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null)
      return
    }
    setIsSearching(true)
    try {
      const results = await researchApi.search(searchQuery)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsSearching(false)
    }
  }

  const handleCreate = async () => {
    if (!formData.title || !formData.content) return
    try {
      await researchApi.create({
        title: formData.title,
        source_url: formData.source_url || undefined,
        source_type: formData.source_type,
        content: formData.content,
        category: formData.category || undefined,
        tags: formData.tags ? formData.tags.split(',').map(t => t.trim()) : []
      })
      await loadData()
      setIsAddingItem(false)
      setFormData({ title: '', source_url: '', source_type: 'web', content: '', category: '', tags: '' })
    } catch (error) {
      console.error('Failed to create:', error)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await researchApi.delete(id)
      setItems(items.filter(i => i.id !== id))
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const handleToggleVerified = async (item: ResearchItem) => {
    try {
      await researchApi.update(item.id, { is_verified: !item.is_verified })
      setItems(items.map(i => i.id === item.id ? { ...i, is_verified: !i.is_verified } : i))
    } catch (error) {
      console.error('Failed to update:', error)
    }
  }

  const getSourceTypeIcon = (type: string) => {
    switch (type) {
      case 'web': return <ExternalLink className="w-4 h-4" />
      case 'book': return <BookOpen className="w-4 h-4" />
      default: return <Library className="w-4 h-4" />
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 p-6 border-b border-border bg-gradient-to-r from-emerald-900/20 to-teal-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20">
              <Library className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">Research Library</h1>
              <p className="text-muted-foreground">Store and organize your research materials</p>
            </div>
          </div>
          
          <button
            onClick={() => setIsAddingItem(true)}
            className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Research
          </button>
        </div>

        {/* Search */}
        <div className="mt-4 flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search research by content..."
              className="w-full pl-10 pr-4 py-2 bg-card border border-border rounded-lg"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={isSearching}
            className="px-4 py-2 bg-muted hover:bg-muted/80 rounded-lg flex items-center gap-2"
          >
            {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </button>
          {searchResults && (
            <button
              onClick={() => setSearchResults(null)}
              className="px-4 py-2 border border-border rounded-lg"
            >
              Clear
            </button>
          )}
        </div>

        {/* Category Filter */}
        <div className="mt-4 flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCategory(null)}
            className={cn(
              "px-3 py-1.5 rounded-full text-sm flex items-center gap-1",
              !selectedCategory 
                ? "bg-emerald-500 text-white" 
                : "bg-muted text-muted-foreground hover:text-foreground"
            )}
          >
            <Filter className="w-3 h-3" />
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat.name}
              onClick={() => setSelectedCategory(cat.name)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm",
                selectedCategory === cat.name 
                  ? "bg-emerald-500 text-white" 
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              {cat.name} ({cat.count})
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* Add Form */}
        {isAddingItem && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 bg-card border border-border rounded-xl p-6"
          >
            <h3 className="text-lg font-semibold mb-4">Add Research Item</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-sm text-muted-foreground mb-1">Title *</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="Research title"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Source URL</label>
                <input
                  type="url"
                  value={formData.source_url}
                  onChange={(e) => setFormData({ ...formData, source_url: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Source Type</label>
                <select
                  value={formData.source_type}
                  onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                >
                  <option value="web">Web</option>
                  <option value="book">Book</option>
                  <option value="article">Article</option>
                  <option value="personal_note">Personal Note</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Category</label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="e.g., historical, cultural"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-1">Tags (comma separated)</label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2"
                  placeholder="tag1, tag2, tag3"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-muted-foreground mb-1">Content *</label>
                <textarea
                  value={formData.content}
                  onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                  className="w-full bg-muted border border-border rounded-lg px-4 py-2 resize-none"
                  rows={5}
                  placeholder="Research content, notes, or extracted information..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setIsAddingItem(false)}
                className="px-4 py-2 border border-border rounded-lg hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!formData.title || !formData.content}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg disabled:opacity-50"
              >
                Save Research
              </button>
            </div>
          </motion.div>
        )}

        {/* Search Results */}
        {searchResults && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold mb-3">Search Results ({searchResults.length})</h3>
            <div className="space-y-2">
              {searchResults.map(result => (
                <div
                  key={result.id}
                  onClick={() => setExpandedItemId(result.id)}
                  className="p-4 bg-card border border-border rounded-lg cursor-pointer hover:border-emerald-500/50"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{result.title}</span>
                    <span className="text-sm text-emerald-400">{(result.similarity * 100).toFixed(0)}% match</span>
                  </div>
                  {result.summary && <p className="text-sm text-muted-foreground mt-1">{result.summary}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Items List */}
        {items.length === 0 ? (
          <div className="text-center text-muted-foreground py-12 border border-dashed border-border rounded-lg">
            <Library className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No research items yet. Add your first one above!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item, index) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.03 }}
                className={cn(
                  "bg-card border rounded-xl overflow-hidden transition-all cursor-pointer",
                  expandedItemId === item.id ? "border-emerald-500" : "border-border hover:border-emerald-500/50"
                )}
                onClick={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {getSourceTypeIcon(item.source_type)}
                      <h3 className="font-medium line-clamp-1">{item.title}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleToggleVerified(item) }}
                        className={cn(
                          "p-1.5 rounded-lg",
                          item.is_verified 
                            ? "text-emerald-400 bg-emerald-500/20" 
                            : "text-muted-foreground hover:bg-muted"
                        )}
                        title={item.is_verified ? "Verified" : "Mark as verified"}
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                        className="p-1.5 hover:bg-red-500/20 rounded-lg text-muted-foreground hover:text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  
                  {item.category && (
                    <span className="inline-block mt-2 px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground">
                      {item.category}
                    </span>
                  )}
                  
                  {item.summary && (
                    <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{item.summary}</p>
                  )}
                  
                  {item.tags && item.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {item.tags.slice(0, 3).map((tag, i) => (
                        <span key={i} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-xs">
                          <Tag className="w-2.5 h-2.5" />
                          {tag}
                        </span>
                      ))}
                      {item.tags.length > 3 && (
                        <span className="text-xs text-muted-foreground">+{item.tags.length - 3} more</span>
                      )}
                    </div>
                  )}
                  
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1 mt-2 text-xs text-blue-400 hover:underline"
                    >
                      <Link className="w-3 h-3" />
                      Source
                    </a>
                  )}
                </div>
                
                {/* Expanded content */}
                {expandedItemId === item.id && item.content && (
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: 'auto' }}
                    className="border-t border-border bg-muted/30 p-4"
                  >
                    <p className="text-sm whitespace-pre-wrap">{item.content}</p>
                  </motion.div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

