import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { sessionsApi, chatApi, type Session, type Message, type ChatResponse } from '@/lib/api'
import { useSettingsStore } from './settingsStore'

interface ChatState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  
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
      set({ messages, isLoading: false })
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
    
    // Add user message immediately
    const userMessage: Message = {
      id: Date.now(),
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
        categories: state.categories.length > 0 ? state.categories : undefined
      })
      
      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.message,
        metadata: { sources: response.sources },
        created_at: new Date().toISOString()
      }
      
      set((s) => ({ 
        messages: [...s.messages, assistantMessage],
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
    
    // Add user message immediately
    const userMessage: Message = {
      id: Date.now(),
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
          categories: state.categories.length > 0 ? state.categories : undefined
        })
      })
      
      if (!response.ok) throw new Error('Stream request failed')
      
      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader available')
      
      const decoder = new TextDecoder()
      let assistantContent = ''
      let sessionId = state.currentSessionId
      
      // Add placeholder assistant message
      const assistantMessage: Message = {
        id: Date.now() + 1,
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
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
      
      set({ currentSessionId: sessionId, isStreaming: false, uploadedContent: null, uploadedFilename: null })
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
  
  clearError: () => set({ error: null })
}))

