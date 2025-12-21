import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Language } from '@/lib/i18n'

export const KNOWLEDGE_CATEGORIES = [
  'character',
  'plot',
  'setting',
  'worldbuilding',
  'timeline',
  'dialogue',
  'research',
  'notes'
] as const

export type KnowledgeCategory = typeof KNOWLEDGE_CATEGORIES[number]

interface SettingsState {
  language: Language
  maxContextTokens: number
  activeCategories: KnowledgeCategory[]
  characterAwareness: boolean
  
  setLanguage: (lang: Language) => void
  setMaxContextTokens: (tokens: number) => void
  toggleCategory: (category: KnowledgeCategory) => void
  setCharacterAwareness: (value: boolean) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      language: 'en',
      maxContextTokens: 32000,
      activeCategories: [...KNOWLEDGE_CATEGORIES],
      characterAwareness: true,
      
      setLanguage: (language) => set({ language }),
      setMaxContextTokens: (maxContextTokens) => set({ maxContextTokens }),
      toggleCategory: (category) => set((state) => ({
        activeCategories: state.activeCategories.includes(category)
          ? state.activeCategories.filter(c => c !== category)
          : [...state.activeCategories, category]
      })),
      setCharacterAwareness: (characterAwareness) => set({ characterAwareness }),
    }),
    {
      name: 'novel-rag-settings',
    }
  )
)
