import { useState, useEffect, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, Database, MessageSquare, FileText, Trash2, Search, X,
  CheckCircle, Clock, Users, Globe, Sparkles, Lightbulb, Library,
  Edit3, Save, XCircle, Wand2, Eye, ArrowRight, Check, RotateCcw,
  Filter, ChevronDown, ChevronUp, Copy, Download, Tag, Layers,
  BookOpen, Map, Swords, Crown, Heart, Zap, GitCompare, CheckSquare,
  Square, Loader2, RefreshCw, SortAsc, SortDesc, Grid, List
} from 'lucide-react'
import { knowledgeApi, searchApi, storyApi, type Knowledge, type SearchResponse, type Series, type KnowledgeUpdate, type AIImproveRequest, type AIImproveResponse } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import { KnowledgeCategoryPicker, SIMPLIFIED_CATEGORIES, getBackendCategory, type SimplifiedCategory } from '@/components/KnowledgeCategoryPicker'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type Tab = 'knowledge' | 'characters' | 'world_rules' | 'foreshadowing' | 'facts'
type ViewMode = 'grid' | 'list'
type SortMode = 'newest' | 'oldest' | 'title' | 'category'

interface StoryElement {
  id: number
  name?: string
  title?: string
  description?: string
  verification_status?: string
  auto_extracted?: boolean
  created_at: string
  [key: string]: any
}

// Category configuration with icons and colors
const CATEGORY_CONFIG: Record<string, { icon: any; color: string; label: string; labelZh: string }> = {
  worldbuilding: { icon: Globe, color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', label: 'Worldbuilding', labelZh: '世界觀' },
  worldbuilding_raw: { icon: BookOpen, color: 'bg-teal-500/20 text-teal-400 border-teal-500/30', label: 'Raw Import', labelZh: '原始導入' },
  character: { icon: Users, color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'Character', labelZh: '角色' },
  settings: { icon: Map, color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'Settings', labelZh: '設定' },
  plot: { icon: Layers, color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', label: 'Plot', labelZh: '情節' },
  chapter: { icon: BookOpen, color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30', label: 'Chapter', labelZh: '章節' },
  dialogue: { icon: MessageSquare, color: 'bg-pink-500/20 text-pink-400 border-pink-500/30', label: 'Dialogue', labelZh: '對話' },
  concept: { icon: Lightbulb, color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', label: 'Concept', labelZh: '概念' },
  draft: { icon: Edit3, color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', label: 'Draft', labelZh: '草稿' },
  research: { icon: Search, color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', label: 'Research', labelZh: '研究' },
  notes: { icon: FileText, color: 'bg-gray-500/20 text-gray-400 border-gray-500/30', label: 'Notes', labelZh: '筆記' },
  artifact: { icon: Crown, color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', label: 'Artifact', labelZh: '器物' },
  faction: { icon: Swords, color: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'Faction', labelZh: '勢力' },
  cultivation_realm: { icon: Zap, color: 'bg-violet-500/20 text-violet-400 border-violet-500/30', label: 'Cultivation', labelZh: '修煉境界' },
  foreshadowing: { icon: Sparkles, color: 'bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/30', label: 'Foreshadowing', labelZh: '伏筆' },
  document: { icon: FileText, color: 'bg-green-500/20 text-green-400 border-green-500/30', label: 'Document', labelZh: '文檔' },
  chat: { icon: MessageSquare, color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'Chat', labelZh: '對話' },
  idea: { icon: Lightbulb, color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', label: 'Idea', labelZh: '想法' },
  smart_import: { icon: Wand2, color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', label: 'Smart Import', labelZh: '智能導入' },
  raw_import: { icon: FileText, color: 'bg-teal-500/20 text-teal-400 border-teal-500/30', label: 'Raw Import', labelZh: '原始導入' },
}

const getCategoryConfig = (category: string) => {
  return CATEGORY_CONFIG[category] || CATEGORY_CONFIG['notes']
}

// Diff component for side-by-side comparison
function DiffViewer({ original, suggested }: { original: string; suggested: string }) {
  const [showDiff, setShowDiff] = useState(true)
  
  // Simple diff: split into lines and compare
  const originalLines = original.split('\n')
  const suggestedLines = suggested.split('\n')
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setShowDiff(!showDiff)}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <GitCompare className="w-4 h-4" />
          {showDiff ? 'Hide Diff View' : 'Show Diff View'}
        </button>
      </div>
      
      {showDiff ? (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
            <p className="text-xs text-red-400 mb-2 font-medium">Original</p>
            <div className="text-sm text-foreground/80 whitespace-pre-wrap max-h-48 overflow-y-auto">
              {original}
            </div>
          </div>
          <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-lg">
            <p className="text-xs text-green-400 mb-2 font-medium">Suggested</p>
            <div className="text-sm text-foreground whitespace-pre-wrap max-h-48 overflow-y-auto">
              {suggested}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-3 bg-muted/50 rounded-lg text-sm text-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">
          {suggested}
        </div>
      )}
    </div>
  )
}

// Pagination component
function Pagination({ 
  currentPage, 
  totalPages, 
  onPageChange 
}: { 
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void 
}) {
  if (totalPages <= 1) return null
  
  const pages = []
  const maxVisible = 5
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
  let end = Math.min(totalPages, start + maxVisible - 1)
  
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1)
  }
  
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }
  
  return (
    <div className="flex items-center justify-center gap-2 mt-6">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-3 py-1.5 rounded-lg text-sm bg-muted hover:bg-muted/80 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Previous
      </button>
      
      {start > 1 && (
        <>
          <button
            onClick={() => onPageChange(1)}
            className="px-3 py-1.5 rounded-lg text-sm bg-muted hover:bg-muted/80"
          >
            1
          </button>
          {start > 2 && <span className="text-muted-foreground">...</span>}
        </>
      )}
      
      {pages.map(page => (
        <button
          key={page}
          onClick={() => onPageChange(page)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-sm transition-colors",
            page === currentPage
              ? "bg-primary text-primary-foreground"
              : "bg-muted hover:bg-muted/80"
          )}
        >
          {page}
        </button>
      ))}
      
      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span className="text-muted-foreground">...</span>}
          <button
            onClick={() => onPageChange(totalPages)}
            className="px-3 py-1.5 rounded-lg text-sm bg-muted hover:bg-muted/80"
          >
            {totalPages}
          </button>
        </>
      )}
      
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-3 py-1.5 rounded-lg text-sm bg-muted hover:bg-muted/80 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Next
      </button>
    </div>
  )
}

export function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<Tab>('knowledge')
  const [knowledge, setKnowledge] = useState<Knowledge[]>([])
  const [characters, setCharacters] = useState<StoryElement[]>([])
  const [worldRules, setWorldRules] = useState<StoryElement[]>([])
  const [foreshadowing, setForeshadowing] = useState<StoryElement[]>([])
  const [facts, setFacts] = useState<StoryElement[]>([])
  
  const [filter, setFilter] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [verificationFilter, setVerificationFilter] = useState<string | null>('approved')
  const [searchQuery, setSearchQuery] = useState('')
  const [localSearch, setLocalSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [formData, setFormData] = useState({ source_type: 'document', title: '', content: '', tags: '', category: '' })
  const [loading, setLoading] = useState(true)
  
  // View settings
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [sortMode, setSortMode] = useState<SortMode>('newest')
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(24)
  
  // Bulk selection
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set())
  const [isBulkMode, setIsBulkMode] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  
  // Editing state
  const [editingItem, setEditingItem] = useState<Knowledge | null>(null)
  const [editFormData, setEditFormData] = useState({ title: '', content: '', tags: '' })
  const [isSaving, setIsSaving] = useState(false)
  
  // Detail/AI Improve modal state
  const [detailItem, setDetailItem] = useState<Knowledge | null>(null)
  const [isAskingAI, setIsAskingAI] = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState<AIImproveResponse | null>(null)
  const [selectedImprovementType, setSelectedImprovementType] = useState<AIImproveRequest['improvement_type']>('general')
  
  // Series selector
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  
  // Category dropdown
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false)

  // Get unique categories from knowledge
  const uniqueCategories = useMemo(() => {
    const cats = new Set(knowledge.map(k => k.source_type || k.category || 'notes'))
    return Array.from(cats).sort()
  }, [knowledge])

  // Filter and sort knowledge
  const filteredKnowledge = useMemo(() => {
    let items = [...knowledge]
    
    // Category filter
    if (categoryFilter) {
      items = items.filter(k => (k.source_type || k.category) === categoryFilter)
    }
    
    // Source type filter
    if (filter) {
      items = items.filter(k => k.source_type === filter)
    }
    
    // Local search filter
    if (localSearch.trim()) {
      const query = localSearch.toLowerCase()
      items = items.filter(k => 
        (k.title?.toLowerCase().includes(query)) ||
        (k.content?.toLowerCase().includes(query)) ||
        (k.tags?.some(t => t.toLowerCase().includes(query)))
      )
    }
    
    // Sort
    switch (sortMode) {
      case 'newest':
        items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        break
      case 'oldest':
        items.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        break
      case 'title':
        items.sort((a, b) => (a.title || '').localeCompare(b.title || ''))
        break
      case 'category':
        items.sort((a, b) => (a.source_type || '').localeCompare(b.source_type || ''))
        break
    }
    
    return items
  }, [knowledge, categoryFilter, filter, localSearch, sortMode])

  // Pagination
  const totalPages = Math.ceil(filteredKnowledge.length / itemsPerPage)
  const paginatedKnowledge = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return filteredKnowledge.slice(start, start + itemsPerPage)
  }, [filteredKnowledge, currentPage, itemsPerPage])

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [categoryFilter, filter, localSearch, sortMode])

  useEffect(() => {
    loadSeriesList()
  }, [])

  useEffect(() => {
    if (selectedSeriesId) {
      loadStoryElements()
      loadPendingCount()
    }
  }, [selectedSeriesId, activeTab, verificationFilter])

  useEffect(() => {
    if (activeTab === 'knowledge') {
      loadKnowledge()
    }
  }, [filter, activeTab])

  const loadSeriesList = async () => {
    try {
      const data = await storyApi.listSeries()
      setSeriesList(data)
      if (data.length > 0) {
        setSelectedSeriesId(data[0].id)
      }
    } catch (error) {
      console.error('Failed to load series:', error)
    }
  }

  const loadPendingCount = async () => {
    if (!selectedSeriesId) return
    try {
      const res = await fetch(`${API_BASE}/verification/stats/${selectedSeriesId}`)
      const data = await res.json()
      setPendingCount(data.total_pending || 0)
    } catch (error) {
      console.error('Failed to load pending count:', error)
    }
  }

  const loadStoryElements = async () => {
    if (!selectedSeriesId) return
    setLoading(true)
    
    try {
      if (activeTab === 'characters') {
        const res = await fetch(`${API_BASE}/story/characters/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setCharacters(data)
      } else if (activeTab === 'world_rules') {
        const res = await fetch(`${API_BASE}/story/world-rules/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setWorldRules(data)
      } else if (activeTab === 'foreshadowing') {
        const res = await fetch(`${API_BASE}/story/foreshadowing/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setForeshadowing(data)
      } else if (activeTab === 'facts') {
        const res = await fetch(`${API_BASE}/story/facts/${selectedSeriesId}?status=${verificationFilter || 'all'}`)
        const data = await res.json()
        setFacts(data)
      }
    } catch (error) {
      console.error('Failed to load story elements:', error)
    }
    setLoading(false)
  }

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
      const backendCategory = formData.category 
        ? getBackendCategory(formData.category, formData.content)
        : formData.source_type
      
      await knowledgeApi.create({
        source_type: backendCategory,
        title: formData.title,
        content: formData.content,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
      })
      setIsCreating(false)
      setFormData({ source_type: 'document', title: '', content: '', tags: '', category: '' })
      loadKnowledge()
    } catch (error) {
      console.error('Failed to create:', error)
    }
  }

  const handleCategorySelect = (category: SimplifiedCategory) => {
    setFormData({ 
      ...formData, 
      category: category.id,
      source_type: category.backendCategories[0]
    })
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

  // Bulk operations
  const handleSelectItem = (id: number) => {
    const newSelected = new Set(selectedItems)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedItems(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedItems.size === paginatedKnowledge.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(paginatedKnowledge.map(k => k.id)))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return
    if (!confirm(`Delete ${selectedItems.size} items? This cannot be undone.`)) return
    
    setIsBulkDeleting(true)
    try {
      await Promise.all(Array.from(selectedItems).map(id => knowledgeApi.delete(id)))
      setSelectedItems(new Set())
      setIsBulkMode(false)
      loadKnowledge()
    } catch (error) {
      console.error('Bulk delete failed:', error)
      alert('Some items failed to delete')
    }
    setIsBulkDeleting(false)
  }

  const handleCopyToClipboard = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
    } catch (error) {
      console.error('Copy failed:', error)
    }
  }

  const handleEdit = (item: Knowledge) => {
    setEditingItem(item)
    setEditFormData({
      title: item.title || '',
      content: item.content || '',
      tags: item.tags?.join(', ') || ''
    })
  }

  const handleCancelEdit = () => {
    setEditingItem(null)
    setEditFormData({ title: '', content: '', tags: '' })
  }

  const handleSaveEdit = async () => {
    if (!editingItem) return
    setIsSaving(true)
    try {
      const updateData: KnowledgeUpdate = {
        title: editFormData.title || undefined,
        content: editFormData.content || undefined,
        tags: editFormData.tags ? editFormData.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined
      }
      await knowledgeApi.update(editingItem.id, updateData)
      setEditingItem(null)
      setEditFormData({ title: '', content: '', tags: '' })
      loadKnowledge()
    } catch (error) {
      console.error('Failed to update:', error)
      alert('Failed to save changes')
    }
    setIsSaving(false)
  }

  const handleViewDetail = async (item: Knowledge) => {
    try {
      const fullItem = await knowledgeApi.get(item.id)
      setDetailItem(fullItem)
      setAiSuggestion(null)
    } catch (error) {
      console.error('Failed to fetch item:', error)
      setDetailItem(item)
    }
  }

  const handleAskAIImprove = async () => {
    if (!detailItem) return
    setIsAskingAI(true)
    try {
      const response = await knowledgeApi.askAIImprove(detailItem.id, {
        improvement_type: selectedImprovementType,
        language: 'zh-TW'
      })
      setAiSuggestion(response)
    } catch (error) {
      console.error('AI improvement failed:', error)
      alert('AI improvement request failed')
    }
    setIsAskingAI(false)
  }

  const handleApplyAISuggestion = async () => {
    if (!detailItem || !aiSuggestion) return
    setIsSaving(true)
    try {
      const updateData: KnowledgeUpdate = {
        content: aiSuggestion.suggested_content
      }
      if (aiSuggestion.suggested_title) {
        updateData.title = aiSuggestion.suggested_title
      }
      await knowledgeApi.update(detailItem.id, updateData)
      
      const updated = await knowledgeApi.get(detailItem.id)
      setDetailItem(updated)
      setAiSuggestion(null)
      loadKnowledge()
    } catch (error) {
      console.error('Failed to apply suggestion:', error)
      alert('Failed to apply AI suggestion')
    }
    setIsSaving(false)
  }

  const handleCloseDetail = () => {
    setDetailItem(null)
    setAiSuggestion(null)
  }

  const getVerificationBadge = (status?: string, autoExtracted?: boolean) => {
    if (status === 'pending') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-xs">
          <Clock className="w-3 h-3" />
          Pending
        </span>
      )
    }
    if (autoExtracted) {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-xs">
          <Sparkles className="w-3 h-3" />
          Auto
        </span>
      )
    }
    return (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-xs">
        <CheckCircle className="w-3 h-3" />
        Approved
      </span>
    )
  }

  const tabs = [
    { id: 'knowledge' as Tab, label: 'Knowledge Base', icon: Database, count: knowledge.length },
    { id: 'characters' as Tab, label: 'Characters', icon: Users, count: characters.length },
    { id: 'world_rules' as Tab, label: 'World Rules', icon: Globe, count: worldRules.length },
    { id: 'foreshadowing' as Tab, label: 'Foreshadowing', icon: Sparkles, count: foreshadowing.length },
    { id: 'facts' as Tab, label: 'Story Facts', icon: Lightbulb, count: facts.length },
  ]

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-display font-semibold text-foreground">
              Knowledge Base
            </h1>
            <p className="text-muted-foreground">
              {filteredKnowledge.length} items {categoryFilter && `in ${getCategoryConfig(categoryFilter).labelZh}`}
            </p>
          </div>
          
          {seriesList.length > 0 && activeTab !== 'knowledge' && (
            <div className="flex items-center gap-2 ml-4 p-2 bg-card rounded-lg border border-border">
              <Library className="w-4 h-4 text-muted-foreground" />
              <select
                value={selectedSeriesId || ''}
                onChange={(e) => setSelectedSeriesId(Number(e.target.value))}
                className="bg-transparent border-none text-sm focus:outline-none"
              >
                {seriesList.map(s => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
            </div>
          )}
          
          {pendingCount > 0 && (
            <a 
              href="/verification"
              className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors"
            >
              <Clock className="w-4 h-4" />
              {pendingCount} pending review
            </a>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {/* Bulk Mode Toggle */}
          {activeTab === 'knowledge' && (
            <button
              onClick={() => {
                setIsBulkMode(!isBulkMode)
                setSelectedItems(new Set())
              }}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-lg transition-colors",
                isBulkMode 
                  ? "bg-primary/20 text-primary" 
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
            >
              <CheckSquare className="w-4 h-4" />
              <span className="text-sm font-medium">Bulk</span>
            </button>
          )}
          
          {activeTab === 'knowledge' && (
            <button
              onClick={() => setIsCreating(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span className="font-medium">Add Knowledge</span>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
              <span className="ml-1 px-2 py-0.5 rounded bg-muted text-xs">
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Knowledge Tab Controls */}
      {activeTab === 'knowledge' && (
        <div className="space-y-4 mb-4">
          {/* Search & Filter Row */}
          <div className="flex gap-4 flex-wrap items-center">
            {/* Local Search */}
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Filter knowledge... / 篩選知識..."
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
              {localSearch && (
                <button
                  onClick={() => setLocalSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                >
                  <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
                </button>
              )}
            </div>
            
            {/* Category Filter */}
            <div className="relative">
              <button
                onClick={() => setShowCategoryDropdown(!showCategoryDropdown)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted border border-border hover:bg-muted/80 transition-colors"
              >
                <Filter className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">
                  {categoryFilter ? getCategoryConfig(categoryFilter).labelZh : 'All Categories'}
                </span>
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              </button>
              
              {showCategoryDropdown && (
                <>
                  <div 
                    className="fixed inset-0 z-10"
                    onClick={() => setShowCategoryDropdown(false)}
                  />
                  <div className="absolute top-full mt-2 left-0 z-20 w-64 bg-card border border-border rounded-xl shadow-xl overflow-hidden">
                    <div className="max-h-80 overflow-y-auto p-2">
                      <button
                        onClick={() => {
                          setCategoryFilter(null)
                          setShowCategoryDropdown(false)
                        }}
                        className={cn(
                          "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors",
                          !categoryFilter ? "bg-primary/20 text-primary" : "hover:bg-muted"
                        )}
                      >
                        <Layers className="w-4 h-4" />
                        <span className="text-sm">All Categories</span>
                        <span className="ml-auto text-xs text-muted-foreground">{knowledge.length}</span>
                      </button>
                      
                      {uniqueCategories.map(cat => {
                        const config = getCategoryConfig(cat)
                        const Icon = config.icon
                        const count = knowledge.filter(k => (k.source_type || k.category) === cat).length
                        
                        return (
                          <button
                            key={cat}
                            onClick={() => {
                              setCategoryFilter(cat)
                              setShowCategoryDropdown(false)
                            }}
                            className={cn(
                              "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors",
                              categoryFilter === cat ? "bg-primary/20 text-primary" : "hover:bg-muted"
                            )}
                          >
                            <Icon className={cn("w-4 h-4", config.color.split(' ')[1])} />
                            <span className="text-sm">{config.labelZh}</span>
                            <span className="ml-auto text-xs text-muted-foreground">{count}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
            
            {/* Sort */}
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as SortMode)}
              className="px-3 py-2 rounded-lg bg-muted border border-border text-sm focus:outline-none"
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="title">By Title</option>
              <option value="category">By Category</option>
            </select>
            
            {/* View Mode */}
            <div className="flex rounded-lg overflow-hidden border border-border">
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  "p-2 transition-colors",
                  viewMode === 'grid' ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "p-2 transition-colors",
                  viewMode === 'list' ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
            
            {/* Refresh */}
            <button
              onClick={loadKnowledge}
              disabled={loading}
              className="p-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={cn("w-4 h-4 text-muted-foreground", loading && "animate-spin")} />
            </button>
          </div>
          
          {/* Bulk Actions Bar */}
          {isBulkMode && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-4 p-3 bg-card border border-border rounded-lg"
            >
              <button
                onClick={handleSelectAll}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
              >
                {selectedItems.size === paginatedKnowledge.length ? (
                  <CheckSquare className="w-4 h-4 text-primary" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
                Select All ({paginatedKnowledge.length})
              </button>
              
              <span className="text-sm text-muted-foreground">
                {selectedItems.size} selected
              </span>
              
              <div className="flex-1" />
              
              <button
                onClick={handleBulkDelete}
                disabled={selectedItems.size === 0 || isBulkDeleting}
                className="flex items-center gap-2 px-3 py-1.5 bg-destructive/20 hover:bg-destructive/30 text-destructive rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isBulkDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Delete Selected
              </button>
              
              <button
                onClick={() => {
                  setIsBulkMode(false)
                  setSelectedItems(new Set())
                }}
                className="p-1.5 hover:bg-muted rounded transition-colors"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </motion.div>
          )}
        </div>
      )}

      {/* Verification Filter (for story elements) */}
      {activeTab !== 'knowledge' && (
        <div className="flex gap-2 mb-4">
          {['approved', 'pending', null].map((status) => (
            <button
              key={status || 'all'}
              onClick={() => setVerificationFilter(status)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                verificationFilter === status
                  ? status === 'pending' 
                    ? "bg-yellow-500/20 text-yellow-400"
                    : status === 'approved'
                    ? "bg-green-500/20 text-green-400"
                    : "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              {status === 'approved' && <CheckCircle className="w-3 h-3" />}
              {status === 'pending' && <Clock className="w-3 h-3" />}
              {status === null ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      )}

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
              <KnowledgeCategoryPicker
                selected={formData.category}
                onSelect={handleCategorySelect}
                language="zh-TW"
              />
              
              {formData.category && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-4 pt-4 border-t border-border"
                >
                  <input
                    type="text"
                    placeholder="Title / 標題"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                  />
                  <textarea
                    placeholder="Content / 內容..."
                    value={formData.content}
                    onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                    rows={6}
                    className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
                  />
                  <input
                    type="text"
                    placeholder="Tags / 標籤 (comma separated)"
                    value={formData.tags}
                    onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                  />
                  <button
                    onClick={handleCreate}
                    disabled={!formData.title || !formData.content}
                    className="w-full px-4 py-3 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                  >
                    Save to World / 保存到世界
                  </button>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : activeTab === 'knowledge' ? (
          <>
            {/* Knowledge Grid/List */}
            <div className={cn(
              viewMode === 'grid' 
                ? "grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                : "space-y-2"
            )}>
              {paginatedKnowledge.map((item) => {
                const config = getCategoryConfig(item.source_type || item.category || 'notes')
                const Icon = config.icon
                const isEditing = editingItem?.id === item.id
                const isSelected = selectedItems.has(item.id)
                
                return viewMode === 'grid' ? (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={cn(
                      "p-4 rounded-xl bg-card border transition-all",
                      isEditing ? "border-primary ring-2 ring-primary/20" : 
                      isSelected ? "border-primary/50 bg-primary/5" :
                      "border-border hover:border-primary/30"
                    )}
                  >
                    {isEditing ? (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-primary">Editing</span>
                          <div className="flex gap-1">
                            <button
                              onClick={handleSaveEdit}
                              disabled={isSaving}
                              className="p-1.5 bg-green-500/20 hover:bg-green-500/30 rounded transition-colors disabled:opacity-50"
                            >
                              <Save className="w-4 h-4 text-green-400" />
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              className="p-1.5 bg-muted hover:bg-muted/80 rounded transition-colors"
                            >
                              <XCircle className="w-4 h-4 text-muted-foreground" />
                            </button>
                          </div>
                        </div>
                        <input
                          type="text"
                          value={editFormData.title}
                          onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground text-sm focus:outline-none focus:border-primary"
                        />
                        <textarea
                          value={editFormData.content}
                          onChange={(e) => setEditFormData({ ...editFormData, content: e.target.value })}
                          rows={6}
                          className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground text-sm focus:outline-none focus:border-primary resize-none"
                        />
                        <input
                          type="text"
                          value={editFormData.tags}
                          onChange={(e) => setEditFormData({ ...editFormData, tags: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground text-sm focus:outline-none focus:border-primary"
                        />
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start justify-between mb-2">
                          <div className={cn("flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs", config.color)}>
                            <Icon className="w-3 h-3" />
                            {config.labelZh}
                          </div>
                          <div className="flex items-center gap-1">
                            {isBulkMode && (
                              <button
                                onClick={() => handleSelectItem(item.id)}
                                className="p-1"
                              >
                                {isSelected ? (
                                  <CheckSquare className="w-4 h-4 text-primary" />
                                ) : (
                                  <Square className="w-4 h-4 text-muted-foreground" />
                                )}
                              </button>
                            )}
                            {!isBulkMode && (
                              <>
                                <button
                                  onClick={() => handleViewDetail(item)}
                                  className="p-1 hover:bg-blue-500/20 rounded transition-colors"
                                  title="View & Improve"
                                >
                                  <Eye className="w-3.5 h-3.5 text-blue-400" />
                                </button>
                                <button
                                  onClick={() => handleEdit(item)}
                                  className="p-1 hover:bg-primary/20 rounded transition-colors"
                                  title="Quick Edit"
                                >
                                  <Edit3 className="w-3.5 h-3.5 text-primary" />
                                </button>
                                <button
                                  onClick={() => handleCopyToClipboard(item.content || '')}
                                  className="p-1 hover:bg-muted rounded transition-colors"
                                  title="Copy"
                                >
                                  <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                                </button>
                                <button
                                  onClick={() => handleDelete(item.id)}
                                  className="p-1 hover:bg-destructive/20 rounded transition-colors"
                                  title="Delete"
                                >
                                  <Trash2 className="w-3.5 h-3.5 text-destructive" />
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                        <h3 className="font-medium text-foreground mb-1 line-clamp-1">
                          {item.title || 'Untitled'}
                        </h3>
                        <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                          {item.content}
                        </p>
                        {item.tags && item.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {item.tags.slice(0, 3).map((tag) => (
                              <span key={tag} className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                                {tag}
                              </span>
                            ))}
                            {item.tags.length > 3 && (
                              <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                                +{item.tags.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                        <p className="text-xs text-muted-foreground">
                          {formatDate(item.created_at)}
                        </p>
                      </>
                    )}
                  </motion.div>
                ) : (
                  /* List View */
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={cn(
                      "flex items-center gap-4 p-3 rounded-lg bg-card border transition-all",
                      isSelected ? "border-primary/50 bg-primary/5" : "border-border hover:border-primary/30"
                    )}
                  >
                    {isBulkMode && (
                      <button onClick={() => handleSelectItem(item.id)}>
                        {isSelected ? (
                          <CheckSquare className="w-5 h-5 text-primary" />
                        ) : (
                          <Square className="w-5 h-5 text-muted-foreground" />
                        )}
                      </button>
                    )}
                    
                    <div className={cn("flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs shrink-0", config.color)}>
                      <Icon className="w-3 h-3" />
                      {config.labelZh}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-foreground truncate">
                        {item.title || 'Untitled'}
                      </h3>
                      <p className="text-sm text-muted-foreground truncate">
                        {item.content}
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {formatDate(item.created_at)}
                      </span>
                      {!isBulkMode && (
                        <>
                          <button
                            onClick={() => handleViewDetail(item)}
                            className="p-1.5 hover:bg-blue-500/20 rounded transition-colors"
                          >
                            <Eye className="w-4 h-4 text-blue-400" />
                          </button>
                          <button
                            onClick={() => handleEdit(item)}
                            className="p-1.5 hover:bg-primary/20 rounded transition-colors"
                          >
                            <Edit3 className="w-4 h-4 text-primary" />
                          </button>
                          <button
                            onClick={() => handleDelete(item.id)}
                            className="p-1.5 hover:bg-destructive/20 rounded transition-colors"
                          >
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </button>
                        </>
                      )}
                    </div>
                  </motion.div>
                )
              })}
              
              {paginatedKnowledge.length === 0 && (
                <div className="col-span-full text-center py-12 text-muted-foreground">
                  <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No knowledge entries found</p>
                  {(categoryFilter || localSearch) && (
                    <button
                      onClick={() => {
                        setCategoryFilter(null)
                        setLocalSearch('')
                      }}
                      className="mt-2 text-primary hover:underline"
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              )}
            </div>
            
            {/* Pagination */}
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          </>
        ) : activeTab === 'characters' ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {characters.map((char) => (
              <motion.div
                key={char.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-blue-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-400" />
                    <h3 className="font-medium text-foreground">{char.name}</h3>
                  </div>
                  {getVerificationBadge(char.verification_status, char.auto_extracted)}
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3 mb-2">
                  {char.description || char.personality || 'No description'}
                </p>
                {char.first_appearance_chapter && (
                  <p className="text-xs text-muted-foreground">
                    First appears: Chapter {char.first_appearance_chapter}
                  </p>
                )}
              </motion.div>
            ))}
            {characters.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No characters found</p>
              </div>
            )}
          </div>
        ) : activeTab === 'world_rules' ? (
          <div className="grid gap-4 md:grid-cols-2">
            {worldRules.map((rule) => (
              <motion.div
                key={rule.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-green-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-green-400" />
                    <span className="px-2 py-0.5 rounded bg-green-500/10 text-green-400 text-xs">
                      {rule.rule_category}
                    </span>
                  </div>
                  {getVerificationBadge(rule.verification_status, rule.auto_extracted)}
                </div>
                <h3 className="font-medium text-foreground mb-1">{rule.rule_name}</h3>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {rule.rule_description}
                </p>
              </motion.div>
            ))}
            {worldRules.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Globe className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No world rules found</p>
              </div>
            )}
          </div>
        ) : activeTab === 'foreshadowing' ? (
          <div className="grid gap-4 md:grid-cols-2">
            {foreshadowing.map((seed) => (
              <motion.div
                key={seed.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={cn(
                  "p-4 rounded-xl border transition-colors",
                  seed.status === 'paid_off' 
                    ? "bg-green-500/5 border-green-500/30" 
                    : "bg-card border-border hover:border-purple-500/30"
                )}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs">
                      {seed.seed_type}
                    </span>
                    {seed.status === 'paid_off' && (
                      <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-xs">
                        Paid Off
                      </span>
                    )}
                  </div>
                  {getVerificationBadge(seed.verification_status, seed.auto_extracted)}
                </div>
                <h3 className="font-medium text-foreground mb-1">{seed.title}</h3>
                <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                  {seed.planted_text}
                </p>
                {seed.intended_payoff && (
                  <p className="text-xs text-muted-foreground italic">
                    → {seed.intended_payoff}
                  </p>
                )}
              </motion.div>
            ))}
            {foreshadowing.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No foreshadowing found</p>
              </div>
            )}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {facts.map((fact) => (
              <motion.div
                key={fact.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-4 rounded-xl bg-card border border-border hover:border-yellow-500/30 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-yellow-400" />
                    <span className="px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 text-xs">
                      {fact.fact_category}
                    </span>
                    {fact.is_secret && (
                      <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 text-xs">
                        Secret
                      </span>
                    )}
                  </div>
                  {getVerificationBadge(fact.verification_status, fact.auto_extracted)}
                </div>
                <p className="text-sm text-foreground">
                  {fact.fact_description}
                </p>
              </motion.div>
            ))}
            {facts.length === 0 && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Lightbulb className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No story facts found</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detail & AI Improve Modal */}
      <AnimatePresence>
        {detailItem && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
            onClick={(e) => e.target === e.currentTarget && handleCloseDetail()}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-border">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    {detailItem.title || 'Untitled'}
                  </h2>
                  <div className="flex items-center gap-2 mt-1">
                    {(() => {
                      const config = getCategoryConfig(detailItem.source_type || 'notes')
                      const Icon = config.icon
                      return (
                        <span className={cn("flex items-center gap-1 px-2 py-0.5 rounded border text-xs", config.color)}>
                          <Icon className="w-3 h-3" />
                          {config.labelZh}
                        </span>
                      )
                    })()}
                    {detailItem.tags?.slice(0, 3).map((tag) => (
                      <span key={tag} className="px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <button
                  onClick={handleCloseDetail}
                  className="p-2 hover:bg-muted rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {/* Content Area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Original Content or Side-by-side diff */}
                {aiSuggestion ? (
                  <DiffViewer
                    original={detailItem.content || ''}
                    suggested={aiSuggestion.suggested_content}
                  />
                ) : (
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-2">Content</h3>
                    <div className="p-4 bg-muted/50 rounded-lg text-sm text-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">
                      {detailItem.content}
                    </div>
                  </div>
                )}

                {/* AI Suggestion Section */}
                {!aiSuggestion && (
                  <div className="border-t border-border pt-4">
                    <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
                      <Wand2 className="w-4 h-4 text-purple-400" />
                      Ask AI to Improve
                    </h3>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {[
                        { id: 'general', label: '整體改進', labelEn: 'General' },
                        { id: 'clarity', label: '清晰度', labelEn: 'Clarity' },
                        { id: 'detail', label: '增加細節', labelEn: 'Add Detail' },
                        { id: 'structure', label: '結構優化', labelEn: 'Structure' },
                        { id: 'consistency', label: '一致性', labelEn: 'Consistency' }
                      ].map((type) => (
                        <button
                          key={type.id}
                          onClick={() => setSelectedImprovementType(type.id as AIImproveRequest['improvement_type'])}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            selectedImprovementType === type.id
                              ? "bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/50"
                              : "bg-muted text-muted-foreground hover:bg-muted/80"
                          )}
                        >
                          {type.label}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={handleAskAIImprove}
                      disabled={isAskingAI}
                      className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                      {isAskingAI ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          AI Analyzing...
                        </>
                      ) : (
                        <>
                          <Wand2 className="w-4 h-4" />
                          Generate Improvement Suggestion
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* AI Suggestion Result */}
                {aiSuggestion && (
                  <div className="border-t border-border pt-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-green-400 flex items-center gap-2">
                        <Sparkles className="w-4 h-4" />
                        AI Suggestion
                      </h3>
                      <button
                        onClick={() => setAiSuggestion(null)}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Try Again
                      </button>
                    </div>

                    {/* Changes Summary */}
                    {aiSuggestion.changes_summary && aiSuggestion.changes_summary.length > 0 && (
                      <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                        <p className="text-sm font-medium text-green-400 mb-2">Changes Made:</p>
                        <ul className="text-sm text-green-300 space-y-1">
                          {aiSuggestion.changes_summary.map((change, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <ArrowRight className="w-3 h-3 mt-1 shrink-0" />
                              {change}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Suggested Title */}
                    {aiSuggestion.suggested_title && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Suggested Title:</p>
                        <p className="text-sm text-foreground font-medium">{aiSuggestion.suggested_title}</p>
                      </div>
                    )}

                    {/* Improvement Notes */}
                    <div className="text-sm text-muted-foreground italic">
                      {aiSuggestion.improvement_notes}
                    </div>

                    {/* Apply Button */}
                    <div className="flex gap-2">
                      <button
                        onClick={handleApplyAISuggestion}
                        disabled={isSaving}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        {isSaving ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Applying...
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            Apply This Suggestion
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => setAiSuggestion(null)}
                        className="px-4 py-3 bg-muted hover:bg-muted/80 text-muted-foreground rounded-lg font-medium transition-colors"
                      >
                        Discard
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="p-4 border-t border-border flex justify-between items-center">
                <p className="text-xs text-muted-foreground">
                  Created: {formatDate(detailItem.created_at)}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleCopyToClipboard(detailItem.content || '')}
                    className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 text-muted-foreground rounded-lg font-medium transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                    Copy
                  </button>
                  <button
                    onClick={() => {
                      handleCloseDetail()
                      handleEdit(detailItem)
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg font-medium transition-colors"
                  >
                    <Edit3 className="w-4 h-4" />
                    Edit Manually
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
