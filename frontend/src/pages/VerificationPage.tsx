/**
 * Verification Hub Page
 * 
 * Review and approve auto-extracted story elements.
 * Items remain in "pending" status until approved here.
 * Only approved items are used in RAG context.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  CheckCircle, 
  XCircle, 
  Edit3, 
  Users, 
  Globe, 
  Sparkles, 
  Target,
  Lightbulb,
  Filter,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface PendingItem {
  id: number;
  item_type: string;
  name: string;
  description: string;
  confidence?: number;
  source?: string;
  created_at: string;
  details: Record<string, any>;
}

interface VerificationStats {
  total_pending: number;
  characters: number;
  world_rules: number;
  foreshadowing: number;
  payoffs: number;
  facts: number;
}

const typeIcons: Record<string, typeof Users> = {
  character: Users,
  world_rule: Globe,
  foreshadowing: Sparkles,
  payoff: Target,
  fact: Lightbulb,
};

const typeColors: Record<string, string> = {
  character: 'border-blue-500/30 bg-blue-500/5',
  world_rule: 'border-green-500/30 bg-green-500/5',
  foreshadowing: 'border-purple-500/30 bg-purple-500/5',
  payoff: 'border-orange-500/30 bg-orange-500/5',
  fact: 'border-yellow-500/30 bg-yellow-500/5',
};

export function VerificationPage() {
  const [seriesId, setSeriesId] = useState<number>(1);
  const [stats, setStats] = useState<VerificationStats | null>(null);
  const [items, setItems] = useState<PendingItem[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<PendingItem | null>(null);
  const [editedData, setEditedData] = useState<Record<string, any>>({});
  const [seriesList, setSeriesList] = useState<{id: number, title: string}[]>([]);

  useEffect(() => {
    loadSeriesList();
  }, []);

  useEffect(() => {
    if (seriesId) {
      loadStats();
      loadItems();
    }
  }, [seriesId, filter]);

  const loadSeriesList = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/story/series`);
      const data = await res.json();
      // Handle both array and object responses
      const seriesArray = Array.isArray(data) ? data : (data.series || []);
      setSeriesList(seriesArray);
      if (seriesArray.length > 0) {
        setSeriesId(seriesArray[0].id);
      }
    } catch (e) {
      console.error('Failed to load series:', e);
    }
  };

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/verification/stats/${seriesId}`);
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  };

  const loadItems = async () => {
    setLoading(true);
    try {
      const url = filter 
        ? `${API_BASE_URL}/verification/pending/${seriesId}?item_type=${filter}`
        : `${API_BASE_URL}/verification/pending/${seriesId}`;
      const res = await fetch(url);
      const data = await res.json();
      setItems(data);
    } catch (e) {
      console.error('Failed to load items:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (item: PendingItem, action: 'approve' | 'reject' | 'edit_and_approve') => {
    try {
      const body: any = { action };
      if (action === 'edit_and_approve') {
        body.edited_data = editedData;
      }

      const res = await fetch(`${API_BASE_URL}/verification/${item.item_type}/${item.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setItems(prev => prev.filter(i => !(i.id === item.id && i.item_type === item.item_type)));
        setEditingItem(null);
        setEditedData({});
        loadStats();
      }
    } catch (e) {
      console.error('Verification failed:', e);
    }
  };

  const handleBulkAction = async (action: 'approve' | 'reject', itemType: string) => {
    const typeItems = items.filter(i => i.item_type === itemType);
    if (typeItems.length === 0) return;

    try {
      const res = await fetch(`${API_BASE_URL}/verification/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_ids: typeItems.map(i => i.id),
          item_type: itemType,
          action
        }),
      });

      if (res.ok) {
        loadItems();
        loadStats();
      }
    } catch (e) {
      console.error('Bulk action failed:', e);
    }
  };

  const startEditing = (item: PendingItem) => {
    setEditingItem(item);
    setEditedData({
      name: item.name,
      description: item.description,
      ...item.details
    });
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return 'text-muted-foreground';
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  // Show message if no series exists
  if (seriesList.length === 0) {
    return (
      <div className="h-full overflow-y-auto p-6 bg-gradient-to-b from-background to-muted/20">
        <div className="max-w-2xl mx-auto text-center py-16">
          <Sparkles className="w-16 h-16 mx-auto mb-6 text-purple-400/50" />
          <h1 className="text-3xl font-bold text-foreground mb-4">Verification Hub</h1>
          <p className="text-muted-foreground mb-6">
            No series found yet. Create a series to start using the Verification Hub.
          </p>
          <p className="text-sm text-muted-foreground mb-8">
            Story elements (characters, world rules, foreshadowing) are automatically extracted 
            when you upload documents or save chapters. They'll appear here for your review.
          </p>
          <div className="space-y-4">
            <a 
              href="/upload"
              className="inline-block px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              Upload a Novel
            </a>
            <p className="text-xs text-muted-foreground">
              Uploading a document will auto-create a series and extract story elements
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 bg-gradient-to-b from-background to-muted/20">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Verification Hub</h1>
            <p className="text-muted-foreground mt-1">
              Review and approve auto-extracted story elements
            </p>
          </div>
          <div className="flex items-center gap-4">
            <select
              value={seriesId}
              onChange={(e) => setSeriesId(Number(e.target.value))}
              className="bg-card border border-border rounded-md px-3 py-2 text-sm"
            >
              {seriesList.map(s => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
            <button 
              onClick={() => { loadStats(); loadItems(); }} 
              className="flex items-center gap-2 px-3 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div 
              className={cn(
                "p-4 rounded-lg border bg-card cursor-pointer transition-all hover:ring-2 ring-primary/50",
                filter === null && "ring-2 ring-primary"
              )}
              onClick={() => setFilter(null)}
            >
              <div className="text-center">
                <div className="text-3xl font-bold text-primary">{stats.total_pending}</div>
                <div className="text-sm text-muted-foreground">Total Pending</div>
              </div>
            </div>
            
            {[
              { key: 'character', label: 'Characters', count: stats.characters },
              { key: 'world_rule', label: 'World Rules', count: stats.world_rules },
              { key: 'foreshadowing', label: 'Foreshadowing', count: stats.foreshadowing },
              { key: 'payoff', label: 'Payoffs', count: stats.payoffs },
              { key: 'fact', label: 'Facts', count: stats.facts },
            ].map(item => {
              const Icon = typeIcons[item.key];
              return (
                <div 
                  key={item.key}
                  className={cn(
                    "p-4 rounded-lg border bg-card cursor-pointer transition-all hover:ring-2 ring-primary/50",
                    filter === item.key && "ring-2 ring-primary"
                  )}
                  onClick={() => setFilter(filter === item.key ? null : item.key)}
                >
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2">
                      <Icon className="w-4 h-4 text-muted-foreground" />
                      <span className="text-2xl font-bold">{item.count}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">{item.label}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Items List */}
        <div className="border rounded-lg bg-card">
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center gap-2 text-lg font-semibold">
              <Filter className="w-5 h-5" />
              {filter ? `${filter.replace('_', ' ').toUpperCase()}S` : 'All Pending Items'}
            </div>
            {filter && items.length > 0 && (
              <div className="flex gap-2">
                <button 
                  onClick={() => handleBulkAction('approve', filter)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-green-500/30 rounded-md text-green-500 hover:bg-green-500/10 transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve All
                </button>
                <button 
                  onClick={() => handleBulkAction('reject', filter)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-red-500/30 rounded-md text-red-500 hover:bg-red-500/10 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  Reject All
                </button>
              </div>
            )}
          </div>
          
          <div className="p-4">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-500/50" />
                <p className="text-lg">All caught up!</p>
                <p className="text-sm">No pending items to verify.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <AnimatePresence>
                  {items.map((item) => {
                    const Icon = typeIcons[item.item_type] || Lightbulb;
                    const isEditing = editingItem?.id === item.id && editingItem?.item_type === item.item_type;
                    
                    return (
                      <motion.div
                        key={`${item.item_type}-${item.id}`}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -100 }}
                        className={cn(
                          "border rounded-lg p-4 transition-all",
                          typeColors[item.item_type]
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <Icon className="w-5 h-5 text-foreground/70" />
                              <h3 className="font-semibold">{item.name}</h3>
                              <span className="text-xs px-2 py-0.5 rounded-full border border-current/30 bg-current/5">
                                {item.item_type.replace('_', ' ')}
                              </span>
                              {item.confidence && (
                                <span className={cn("text-xs", getConfidenceColor(item.confidence))}>
                                  {Math.round(item.confidence * 100)}% confidence
                                </span>
                              )}
                            </div>
                            
                            {!isEditing ? (
                              <>
                                <p className="text-sm mb-2">{item.description}</p>
                                {item.source && (
                                  <p className="text-xs text-muted-foreground">Source: {item.source}</p>
                                )}
                                {Object.entries(item.details).filter(([k, v]) => v && k !== 'source').length > 0 && (
                                  <div className="mt-2 p-2 bg-background/50 rounded text-xs space-y-1">
                                    {Object.entries(item.details)
                                      .filter(([k, v]) => v && k !== 'source')
                                      .map(([key, value]) => (
                                        <div key={key}>
                                          <span className="text-muted-foreground">{key.replace('_', ' ')}: </span>
                                          <span>{String(value)}</span>
                                        </div>
                                      ))}
                                  </div>
                                )}
                              </>
                            ) : (
                              <div className="space-y-3 mt-3 p-3 bg-background/50 rounded-lg">
                                <div>
                                  <label className="text-sm font-medium mb-1 block">Name</label>
                                  <input 
                                    value={editedData.name || ''} 
                                    onChange={(e) => setEditedData({...editedData, name: e.target.value})}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="text-sm font-medium mb-1 block">Description</label>
                                  <textarea 
                                    value={editedData.description || ''} 
                                    onChange={(e) => setEditedData({...editedData, description: e.target.value})}
                                    className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm min-h-[80px]"
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex items-center gap-1 ml-4">
                            {!isEditing ? (
                              <>
                                <button
                                  onClick={() => startEditing(item)}
                                  className="p-2 rounded-md hover:bg-blue-500/10 text-blue-400 transition-colors"
                                  title="Edit"
                                >
                                  <Edit3 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleVerify(item, 'approve')}
                                  className="p-2 rounded-md hover:bg-green-500/10 text-green-400 transition-colors"
                                  title="Approve"
                                >
                                  <CheckCircle className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleVerify(item, 'reject')}
                                  className="p-2 rounded-md hover:bg-red-500/10 text-red-400 transition-colors"
                                  title="Reject"
                                >
                                  <XCircle className="w-4 h-4" />
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  onClick={() => handleVerify(item, 'edit_and_approve')}
                                  className="px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-500 text-white text-sm transition-colors"
                                >
                                  Save & Approve
                                </button>
                                <button
                                  onClick={() => { setEditingItem(null); setEditedData({}); }}
                                  className="px-3 py-1.5 rounded-md border border-border hover:bg-muted text-sm transition-colors"
                                >
                                  Cancel
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>

        {/* Info Card */}
        <div className="border border-dashed border-muted-foreground/30 rounded-lg p-4">
          <div className="flex items-start gap-3 text-sm text-muted-foreground">
            <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground mb-1">How it works</p>
              <p>
                When you save chapters, the AI automatically extracts characters, world rules, 
                foreshadowing seeds, and potential payoffs. These are created as <strong>pending</strong> items 
                and won't be used in RAG context until you approve them here.
              </p>
              <p className="mt-2">
                • <strong>Approve</strong> to include in your story's knowledge base<br/>
                • <strong>Edit & Approve</strong> to correct details before approving<br/>
                • <strong>Reject</strong> to discard false positives
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
