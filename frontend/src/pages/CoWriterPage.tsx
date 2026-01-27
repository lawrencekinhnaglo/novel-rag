import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSettingsStore } from '../store/settingsStore'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface Session {
  id: string
  series_id?: number
  book_id?: number
  chapter_number?: number
  chapter_title?: string
}

type Phase = 'setup' | 'discuss' | 'write' | 'refine'

export default function CoWriterPage() {
  const { language } = useSettingsStore()
  
  // Session state
  const [session, setSession] = useState<Session | null>(null)
  const [phase, setPhase] = useState<Phase>('setup')
  
  // Setup state
  const [seriesId, setSeriesId] = useState<number | undefined>()
  const [bookId, setBookId] = useState<number | undefined>()
  const [chapterNumber, setChapterNumber] = useState<number>(1)
  const [chapterTitle, setChapterTitle] = useState('')
  
  // Discussion state
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  
  // Draft state
  const [currentDraft, setCurrentDraft] = useState('')
  const [draftVersion, setDraftVersion] = useState(0)
  const [wordCount, setWordCount] = useState(0)
  
  // Series list for dropdown
  const [seriesList, setSeriesList] = useState<{id: number, title: string}[]>([])
  const [booksList, setBooksList] = useState<{id: number, title: string}[]>([])
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const draftRef = useRef<HTMLDivElement>(null)
  
  // Load series on mount
  useEffect(() => {
    fetchSeries()
  }, [])
  
  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const fetchSeries = async () => {
    try {
      const res = await fetch(`${API_BASE}/series`)
      if (res.ok) {
        const data = await res.json()
        setSeriesList(data)
      }
    } catch (e) {
      console.error('Failed to fetch series:', e)
    }
  }
  
  const fetchBooks = async (sid: number) => {
    try {
      const res = await fetch(`${API_BASE}/series/${sid}/books`)
      if (res.ok) {
        const data = await res.json()
        setBooksList(data)
      }
    } catch (e) {
      console.error('Failed to fetch books:', e)
    }
  }
  
  const startSession = async () => {
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/writing/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          series_id: seriesId,
          book_id: bookId,
          chapter_number: chapterNumber,
          chapter_title: chapterTitle || undefined
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        setSession({ 
          id: data.session_id, 
          series_id: seriesId, 
          book_id: bookId,
          chapter_number: chapterNumber,
          chapter_title: chapterTitle
        })
        setMessages([{
          role: 'assistant',
          content: data.message,
          timestamp: new Date().toISOString()
        }])
        setPhase('discuss')
      }
    } catch (e) {
      console.error('Failed to start session:', e)
    }
    setIsLoading(false)
  }
  
  const sendMessage = async () => {
    if (!inputMessage.trim() || !session) return
    
    const userMsg = inputMessage.trim()
    setInputMessage('')
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMsg,
      timestamp: new Date().toISOString()
    }])
    
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/writing/discuss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          message: userMsg
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString()
        }])
      }
    } catch (e) {
      console.error('Failed to send message:', e)
    }
    setIsLoading(false)
  }
  
  const generateChapter = async () => {
    if (!session) return
    
    setIsLoading(true)
    setPhase('write')
    
    try {
      const res = await fetch(`${API_BASE}/writing/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        setCurrentDraft(data.content)
        setWordCount(data.word_count)
        setDraftVersion(prev => prev + 1)
        setPhase('refine')
      }
    } catch (e) {
      console.error('Failed to generate chapter:', e)
      setPhase('discuss')
    }
    setIsLoading(false)
  }
  
  const refineDraft = async (instruction: string) => {
    if (!session) return
    
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/writing/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          instruction
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        setCurrentDraft(data.content)
        setWordCount(data.word_count)
        setDraftVersion(prev => prev + 1)
      }
    } catch (e) {
      console.error('Failed to refine:', e)
    }
    setIsLoading(false)
  }
  
  const quickRefine = async (action: string) => {
    if (!session) return
    
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/writing/quick-refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          action
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        setCurrentDraft(data.content)
        setWordCount(data.word_count)
        setDraftVersion(prev => prev + 1)
      }
    } catch (e) {
      console.error('Failed to quick refine:', e)
    }
    setIsLoading(false)
  }
  
  const saveChapter = async () => {
    if (!session) return
    
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/writing/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          title: chapterTitle
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        if (data.success) {
          alert(language === 'zh-TW' ? '章節已保存！' : 'Chapter saved!')
        } else {
          alert(data.error || 'Failed to save')
        }
      }
    } catch (e) {
      console.error('Failed to save:', e)
    }
    setIsLoading(false)
  }
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(currentDraft)
    alert(language === 'zh-TW' ? '已複製到剪貼簿' : 'Copied to clipboard')
  }
  
  // ==================== Render ====================
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900 text-white">
      {/* Header */}
      <header className="border-b border-purple-500/20 bg-black/20 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              ✍️ {language === 'zh-TW' ? '寫作助手' : 'Co-Writer'}
            </h1>
            
            {/* Phase indicator */}
            <div className="flex items-center gap-2 text-sm">
              {['setup', 'discuss', 'write', 'refine'].map((p, i) => (
                <div key={p} className="flex items-center">
                  <span className={`px-2 py-1 rounded ${
                    phase === p 
                      ? 'bg-purple-500 text-white' 
                      : i < ['setup', 'discuss', 'write', 'refine'].indexOf(phase)
                        ? 'bg-green-500/30 text-green-300'
                        : 'bg-slate-700 text-slate-400'
                  }`}>
                    {p === 'setup' && (language === 'zh-TW' ? '設定' : 'Setup')}
                    {p === 'discuss' && (language === 'zh-TW' ? '討論' : 'Discuss')}
                    {p === 'write' && (language === 'zh-TW' ? '撰寫' : 'Write')}
                    {p === 'refine' && (language === 'zh-TW' ? '修改' : 'Refine')}
                  </span>
                  {i < 3 && <span className="mx-1 text-slate-500">→</span>}
                </div>
              ))}
            </div>
          </div>
          
          {session && (
            <div className="text-sm text-slate-400">
              {language === 'zh-TW' ? '會話' : 'Session'}: {session.id}
            </div>
          )}
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto p-4">
        <AnimatePresence mode="wait">
          {/* ==================== Setup Phase ==================== */}
          {phase === 'setup' && (
            <motion.div
              key="setup"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-xl mx-auto mt-20"
            >
              <div className="bg-slate-800/50 rounded-2xl p-8 border border-purple-500/20">
                <h2 className="text-xl font-semibold mb-6 text-center">
                  {language === 'zh-TW' ? '開始新的寫作會話' : 'Start New Writing Session'}
                </h2>
                
                <div className="space-y-4">
                  {/* Series select */}
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">
                      {language === 'zh-TW' ? '系列' : 'Series'} (optional)
                    </label>
                    <select
                      value={seriesId || ''}
                      onChange={(e) => {
                        const val = e.target.value ? parseInt(e.target.value) : undefined
                        setSeriesId(val)
                        if (val) fetchBooks(val)
                      }}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
                    >
                      <option value="">{language === 'zh-TW' ? '-- 選擇系列 --' : '-- Select Series --'}</option>
                      {seriesList.map(s => (
                        <option key={s.id} value={s.id}>{s.title}</option>
                      ))}
                    </select>
                  </div>
                  
                  {/* Book select */}
                  {seriesId && booksList.length > 0 && (
                    <div>
                      <label className="block text-sm text-slate-300 mb-1">
                        {language === 'zh-TW' ? '書籍' : 'Book'} (optional)
                      </label>
                      <select
                        value={bookId || ''}
                        onChange={(e) => setBookId(e.target.value ? parseInt(e.target.value) : undefined)}
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
                      >
                        <option value="">{language === 'zh-TW' ? '-- 選擇書籍 --' : '-- Select Book --'}</option>
                        {booksList.map(b => (
                          <option key={b.id} value={b.id}>{b.title}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  
                  {/* Chapter number */}
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">
                      {language === 'zh-TW' ? '章節號' : 'Chapter Number'}
                    </label>
                    <input
                      type="number"
                      value={chapterNumber}
                      onChange={(e) => setChapterNumber(parseInt(e.target.value) || 1)}
                      min={1}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                  
                  {/* Chapter title */}
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">
                      {language === 'zh-TW' ? '章節標題' : 'Chapter Title'} (optional)
                    </label>
                    <input
                      type="text"
                      value={chapterTitle}
                      onChange={(e) => setChapterTitle(e.target.value)}
                      placeholder={language === 'zh-TW' ? '例：黎明之戰' : 'e.g., The Battle of Dawn'}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                  
                  <button
                    onClick={startSession}
                    disabled={isLoading}
                    className="w-full mt-4 py-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg font-semibold hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50"
                  >
                    {isLoading 
                      ? (language === 'zh-TW' ? '載入中...' : 'Loading...')
                      : (language === 'zh-TW' ? '開始討論 →' : 'Start Discussion →')
                    }
                  </button>
                </div>
              </div>
            </motion.div>
          )}
          
          {/* ==================== Discuss Phase ==================== */}
          {phase === 'discuss' && (
            <motion.div
              key="discuss"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="h-[calc(100vh-12rem)] flex flex-col"
            >
              {/* Messages */}
              <div className="flex-1 overflow-y-auto space-y-4 p-4 bg-slate-800/30 rounded-xl border border-slate-700/50">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-purple-600 text-white' 
                        : 'bg-slate-700 text-slate-100'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-slate-700 rounded-2xl px-4 py-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{animationDelay: '0ms'}}></span>
                        <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}}></span>
                        <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}}></span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
              
              {/* Input */}
              <div className="mt-4 flex gap-2">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder={language === 'zh-TW' 
                    ? '告訴我你想寫什麼... (輸入「開始寫」來生成章節)' 
                    : 'Tell me what you want to write... (type "write" to generate)'
                  }
                  className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 focus:outline-none focus:border-purple-500"
                  disabled={isLoading}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className="px-6 bg-purple-600 hover:bg-purple-700 rounded-xl transition-colors disabled:opacity-50"
                >
                  {language === 'zh-TW' ? '發送' : 'Send'}
                </button>
                <button
                  onClick={generateChapter}
                  disabled={isLoading}
                  className="px-6 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 rounded-xl transition-colors disabled:opacity-50 font-semibold"
                >
                  ✍️ {language === 'zh-TW' ? '開始寫' : 'Write'}
                </button>
              </div>
            </motion.div>
          )}
          
          {/* ==================== Write Phase (Loading) ==================== */}
          {phase === 'write' && (
            <motion.div
              key="write"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-[calc(100vh-12rem)]"
            >
              <div className="text-center">
                <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                <h2 className="text-xl font-semibold mb-2">
                  {language === 'zh-TW' ? '正在撰寫章節...' : 'Writing your chapter...'}
                </h2>
                <p className="text-slate-400">
                  {language === 'zh-TW' ? '根據討論和世界觀生成中，請稍候' : 'Generating based on discussion and worldbuilding'}
                </p>
              </div>
            </motion.div>
          )}
          
          {/* ==================== Refine Phase ==================== */}
          {phase === 'refine' && (
            <motion.div
              key="refine"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex gap-4 h-[calc(100vh-12rem)]"
            >
              {/* Draft display */}
              <div className="flex-1 flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold flex items-center gap-2">
                    📝 {language === 'zh-TW' ? '章節草稿' : 'Draft'} 
                    <span className="text-sm text-slate-400">v{draftVersion}</span>
                    <span className="text-sm text-purple-400">{wordCount} {language === 'zh-TW' ? '字' : 'chars'}</span>
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={copyToClipboard}
                      className="px-3 py-1 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                    >
                      📋 {language === 'zh-TW' ? '複製' : 'Copy'}
                    </button>
                    <button
                      onClick={saveChapter}
                      disabled={isLoading}
                      className="px-3 py-1 text-sm bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
                    >
                      💾 {language === 'zh-TW' ? '保存' : 'Save'}
                    </button>
                  </div>
                </div>
                
                <div 
                  ref={draftRef}
                  className="flex-1 overflow-y-auto bg-slate-800/50 rounded-xl p-6 border border-slate-700/50 whitespace-pre-wrap leading-relaxed text-slate-100"
                >
                  {currentDraft}
                </div>
              </div>
              
              {/* Refine panel */}
              <div className="w-80 flex flex-col">
                <h3 className="font-semibold mb-4">
                  🔧 {language === 'zh-TW' ? '修改選項' : 'Refine Options'}
                </h3>
                
                {/* Quick actions */}
                <div className="space-y-2 mb-6">
                  <p className="text-sm text-slate-400 mb-2">
                    {language === 'zh-TW' ? '快速調整' : 'Quick Actions'}
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => quickRefine('longer')}
                      disabled={isLoading}
                      className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                      📏 {language === 'zh-TW' ? '加長' : 'Longer'}
                    </button>
                    <button
                      onClick={() => quickRefine('shorter')}
                      disabled={isLoading}
                      className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                      ✂️ {language === 'zh-TW' ? '精簡' : 'Shorter'}
                    </button>
                    <button
                      onClick={() => quickRefine('more_dialogue')}
                      disabled={isLoading}
                      className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                      💬 {language === 'zh-TW' ? '更多對話' : 'Dialogue'}
                    </button>
                    <button
                      onClick={() => quickRefine('more_action')}
                      disabled={isLoading}
                      className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors disabled:opacity-50"
                    >
                      ⚔️ {language === 'zh-TW' ? '更多動作' : 'Action'}
                    </button>
                    <button
                      onClick={() => quickRefine('more_emotion')}
                      disabled={isLoading}
                      className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition-colors disabled:opacity-50 col-span-2"
                    >
                      💖 {language === 'zh-TW' ? '加深情感描寫' : 'More Emotion'}
                    </button>
                  </div>
                </div>
                
                {/* Custom refine */}
                <div className="flex-1">
                  <p className="text-sm text-slate-400 mb-2">
                    {language === 'zh-TW' ? '自定義修改' : 'Custom Refinement'}
                  </p>
                  <textarea
                    id="refine-input"
                    placeholder={language === 'zh-TW' 
                      ? '例：把結尾改成懸念、加強主角的內心獨白...' 
                      : 'e.g., Make the ending more suspenseful...'
                    }
                    className="w-full h-32 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500 resize-none"
                  />
                  <button
                    onClick={() => {
                      const input = document.getElementById('refine-input') as HTMLTextAreaElement
                      if (input.value.trim()) {
                        refineDraft(input.value.trim())
                        input.value = ''
                      }
                    }}
                    disabled={isLoading}
                    className="w-full mt-2 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isLoading 
                      ? (language === 'zh-TW' ? '修改中...' : 'Refining...')
                      : (language === 'zh-TW' ? '應用修改' : 'Apply')
                    }
                  </button>
                </div>
                
                {/* Back to discuss */}
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <button
                    onClick={() => setPhase('discuss')}
                    className="w-full py-2 border border-slate-600 rounded-lg hover:bg-slate-800 transition-colors text-sm"
                  >
                    ← {language === 'zh-TW' ? '返回討論' : 'Back to Discussion'}
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
      
      {/* Loading overlay */}
      {isLoading && phase === 'refine' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 flex items-center gap-4">
            <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            <span>{language === 'zh-TW' ? '處理中...' : 'Processing...'}</span>
          </div>
        </div>
      )}
    </div>
  )
}
