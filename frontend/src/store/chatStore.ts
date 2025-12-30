import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { sessionsApi, chatApi, feedbackApi, storyApi, type Session, type Message, type ChatResponse, type LikedQAPair, type FeedbackResponse, type Series } from '@/lib/api'
import { useSettingsStore } from './settingsStore'

interface ChatState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  
  // Series/Story Context
  seriesId: number | null
  seriesTitle: string | null
  availableSeries: Series[]
  
  // Feedback & Liked Context
  likedContext: LikedQAPair[]
  feedbackMap: Record<number, 'like' | 'dislike'>  // assistant_message_id -> feedback
  
  // Settings
  useRag: boolean
  useWebSearch: boolean
  includeGraph: boolean
  provider: 'lm_studio' | 'deepseek' | 'ollama'
  temperature: number
  maxTokens: number
  language: 'en' | 'zh-TW' | 'zh-CN'
  uploadedContent: string | null
  uploadedFilename: string | null
  categories: string[]
  
  // Actions
  loadSessions: () => Promise<void>
  createSession: (title?: string) => Promise<Session>
  selectSession: (id: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  streamMessage: (content: string) => Promise<void>
  
  // Series actions
  loadAvailableSeries: () => Promise<void>
  setSeriesContext: (seriesId: number | null) => Promise<void>
  
  // Feedback actions
  setFeedback: (userMessageId: number, assistantMessageId: number, feedback: 'like' | 'dislike') => Promise<void>
  loadLikedContext: () => Promise<void>
  
  // Settings actions
  setUseRag: (value: boolean) => void
  setUseWebSearch: (value: boolean) => void
  setIncludeGraph: (value: boolean) => void
  setProvider: (value: 'lm_studio' | 'deepseek' | 'ollama') => void
  setTemperature: (value: number) => void
  setMaxTokens: (value: number) => void
  setLanguage: (value: 'en' | 'zh-TW' | 'zh-CN') => void
  setUploadedContent: (content: string | null, filename?: string | null) => void
  setCategories: (categories: string[]) => void
  
  clearError: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,
  
  // Series/Story Context
  seriesId: null,
  seriesTitle: null,
  availableSeries: [],
  
  // Feedback & Liked Context
  likedContext: [],
  feedbackMap: {},
  
  useRag: true,
  useWebSearch: false,
  includeGraph: true,
  provider: 'deepseek',
  temperature: 0.7,
  maxTokens: 8192,
  language: 'en',
  uploadedContent: null,
  uploadedFilename: null,
  categories: [],
  
  loadSessions: async () => {
    try {
      const { sessions } = await sessionsApi.list()
      set({ sessions })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },
  
  createSession: async (title?: string) => {
    try {
      const session = await sessionsApi.create(title)
      set((state) => ({ 
        sessions: [session, ...state.sessions],
        currentSessionId: session.id,
        messages: []
      }))
      return session
    } catch (error) {
      set({ error: (error as Error).message })
      throw error
    }
  },
  
  selectSession: async (id: string) => {
    try {
      set({ isLoading: true, currentSessionId: id })
      const { messages } = await sessionsApi.getMessages(id)
      
      // Load feedback for this session
      try {
        const feedbackList = await feedbackApi.getSessionFeedback(id)
        const feedbackMap: Record<number, 'like' | 'dislike'> = {}
        for (const fb of feedbackList) {
          feedbackMap[fb.assistant_message_id] = fb.feedback_type
        }
        
        // Load liked context
        const likedContext = await feedbackApi.getLikedContext(id)
        
        set({ messages, feedbackMap, likedContext, isLoading: false })
      } catch {
        // If feedback loading fails, just load messages
        set({ messages, isLoading: false })
      }
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },
  
  deleteSession: async (id: string) => {
    try {
      await sessionsApi.delete(id)
      const state = get()
      const newSessions = state.sessions.filter(s => s.id !== id)
      set({ 
        sessions: newSessions,
        currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
        messages: state.currentSessionId === id ? [] : state.messages
      })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },
  
  sendMessage: async (content: string) => {
    const state = get()
    
    // Add user message immediately with temporary ID
    const tempUserMsgId = -Date.now()  // Use negative to distinguish from DB IDs
    const userMessage: Message = {
      id: tempUserMsgId,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    }
    set((s) => ({ messages: [...s.messages, userMessage], isLoading: true }))
    
    try {
      const response: ChatResponse = await chatApi.send({
        session_id: state.currentSessionId || undefined,
        message: content,
        use_rag: state.useRag,
        use_web_search: state.useWebSearch,
        include_graph: state.includeGraph,
        provider: state.provider,
        temperature: state.temperature,
        max_tokens: state.maxTokens,
        language: state.language,
        uploaded_content: state.uploadedContent || undefined,
        categories: state.categories.length > 0 ? state.categories : undefined,
        liked_context: state.likedContext.length > 0 ? state.likedContext : undefined,
        series_id: state.seriesId || undefined  // Add series context
      })
      
      const assistantMessage: Message = {
        id: response.assistant_message_id || -Date.now() - 1,
        role: 'assistant',
        content: response.message,
        metadata: { 
          sources: response.sources,
          user_message_id: response.user_message_id  // Store for feedback
        },
        created_at: new Date().toISOString()
      }
      
      set((s) => ({ 
        // Update user message with real DB ID and add assistant message
        messages: s.messages.map(m => 
          m.id === tempUserMsgId && response.user_message_id
            ? { ...m, id: response.user_message_id }
            : m
        ).concat(assistantMessage),
        currentSessionId: response.session_id,
        isLoading: false,
        uploadedContent: null,  // Clear after sending
        uploadedFilename: null
      }))
      
      // Reload sessions to update message count
      get().loadSessions()
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },
  
  streamMessage: async (content: string) => {
    const state = get()
    
    // Add user message immediately with temporary ID
    const tempUserMsgId = -Date.now()
    const tempAssistantMsgId = -Date.now() - 1
    const userMessage: Message = {
      id: tempUserMsgId,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    }
    set((s) => ({ messages: [...s.messages, userMessage], isStreaming: true }))
    
    try {
      const response = await fetch(chatApi.streamUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.currentSessionId || undefined,
          message: content,
          use_rag: state.useRag,
          use_web_search: state.useWebSearch,
          include_graph: state.includeGraph,
          provider: state.provider,
          temperature: state.temperature,
          max_tokens: state.maxTokens,
          language: state.language,
          uploaded_content: state.uploadedContent || undefined,
          categories: state.categories.length > 0 ? state.categories : undefined,
          liked_context: state.likedContext.length > 0 ? state.likedContext : undefined,
          series_id: state.seriesId || undefined  // Add series context
        })
      })
      
      if (!response.ok) throw new Error('Stream request failed')
      
      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader available')
      
      const decoder = new TextDecoder()
      let assistantContent = ''
      let sessionId = state.currentSessionId
      let userMsgIdFromServer: number | null = null
      let assistantMsgIdFromServer: number | null = null
      
      // Add placeholder assistant message
      const assistantMessage: Message = {
        id: tempAssistantMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }
      set((s) => ({ messages: [...s.messages, assistantMessage] }))
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'session') {
                sessionId = data.session_id
              } else if (data.type === 'content') {
                assistantContent += data.content
                // Update the assistant message content
                set((s) => ({
                  messages: s.messages.map((m, i) => 
                    i === s.messages.length - 1 
                      ? { ...m, content: assistantContent }
                      : m
                  )
                }))
              } else if (data.type === 'done') {
                // Get the real database IDs from the done event
                userMsgIdFromServer = data.user_message_id
                assistantMsgIdFromServer = data.assistant_message_id
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
      
      // Update message IDs to real database IDs
      set((s) => ({
        messages: s.messages.map(m => {
          if (m.id === tempUserMsgId && userMsgIdFromServer) {
            return { ...m, id: userMsgIdFromServer }
          }
          if (m.id === tempAssistantMsgId && assistantMsgIdFromServer) {
            return { 
              ...m, 
              id: assistantMsgIdFromServer,
              metadata: { 
                ...m.metadata,
                user_message_id: userMsgIdFromServer  // Store for feedback
              }
            }
          }
          return m
        }),
        currentSessionId: sessionId, 
        isStreaming: false, 
        uploadedContent: null, 
        uploadedFilename: null
      }))
      get().loadSessions()
    } catch (error) {
      set({ error: (error as Error).message, isStreaming: false })
    }
  },
  
  setUseRag: (value) => set({ useRag: value }),
  setUseWebSearch: (value) => set({ useWebSearch: value }),
  setIncludeGraph: (value) => set({ includeGraph: value }),
  setProvider: (value) => set({ provider: value }),
  setTemperature: (value) => set({ temperature: value }),
  setMaxTokens: (value) => set({ maxTokens: value }),
  setLanguage: (value) => set({ language: value }),
  setUploadedContent: (content, filename = null) => set({ uploadedContent: content, uploadedFilename: filename }),
  setCategories: (categories) => set({ categories }),
  
  // Series actions
  loadAvailableSeries: async () => {
    try {
      const response = await storyApi.listSeries()
      set({ availableSeries: response })
    } catch (error) {
      console.error('Failed to load series:', error)
    }
  },
  
  setSeriesContext: async (seriesId: number | null) => {
    const state = get()
    
    if (seriesId === null) {
      set({ seriesId: null, seriesTitle: null })
      return
    }
    
    // Find the series title
    const series = state.availableSeries.find(s => s.id === seriesId)
    set({ 
      seriesId, 
      seriesTitle: series?.title || `Series ${seriesId}` 
    })
    
    // If we have a current session, link it to the series
    if (state.currentSessionId) {
      try {
        await sessionsApi.linkToSeries(state.currentSessionId, seriesId)
      } catch (error) {
        console.error('Failed to link session to series:', error)
      }
    }
  },
  
  // Feedback actions
  setFeedback: async (userMessageId: number, assistantMessageId: number, feedback: 'like' | 'dislike') => {
    const state = get()
    if (!state.currentSessionId) return
    
    try {
      await feedbackApi.create({
        session_id: state.currentSessionId,
        user_message_id: userMessageId,
        assistant_message_id: assistantMessageId,
        feedback_type: feedback
      })
      
      // Update local feedback map
      set((s) => ({
        feedbackMap: { ...s.feedbackMap, [assistantMessageId]: feedback }
      }))
      
      // Reload liked context
      await get().loadLikedContext()
    } catch (error) {
      console.error('Failed to set feedback:', error)
    }
  },
  
  loadLikedContext: async () => {
    const state = get()
    if (!state.currentSessionId) return
    
    try {
      const likedContext = await feedbackApi.getLikedContext(state.currentSessionId)
      set({ likedContext })
    } catch (error) {
      console.error('Failed to load liked context:', error)
    }
  },
  
  clearError: () => set({ error: null })
}))

