import React from 'react'
import { User, Zap, MapPin, Scale, BookOpen, HelpCircle } from 'lucide-react'

export interface SimplifiedCategory {
  id: string
  label: string
  labelCn: string
  icon: React.ReactNode
  color: string
  examples: string[]
  examplesCn: string[]
  description: string
  descriptionCn: string
  // Maps to existing backend categories
  backendCategories: string[]
}

export const SIMPLIFIED_CATEGORIES: SimplifiedCategory[] = [
  {
    id: 'characters',
    label: 'Characters',
    labelCn: '角色',
    icon: <User className="w-5 h-5" />,
    color: 'bg-purple-500',
    examples: [
      'Character backstory',
      'Personality traits',
      'Relationships',
      'Character arcs'
    ],
    examplesCn: [
      '角色背景故事',
      '性格特徵',
      '人物關係',
      '角色成長軌跡'
    ],
    description: 'Everything about the people in your story',
    descriptionCn: '故事中所有角色的資料',
    backendCategories: ['character', 'character_profile', 'character_arc']
  },
  {
    id: 'powers',
    label: 'Powers & Abilities',
    labelCn: '能力與天賦',
    icon: <Zap className="w-5 h-5" />,
    color: 'bg-yellow-500',
    examples: [
      'Magic systems',
      'Martial arts techniques',
      'Superpowers',
      'Cultivation realms',
      'Bloodline abilities'
    ],
    examplesCn: [
      '魔法體系',
      '武功招式',
      '超能力',
      '修煉境界',
      '血脈能力'
    ],
    description: 'How power works in your world',
    descriptionCn: '你世界中力量的運作方式',
    backendCategories: ['technique', 'talent_system', 'cultivation_realm', 'ability', 'power_system']
  },
  {
    id: 'places',
    label: 'Places & Groups',
    labelCn: '地點與組織',
    icon: <MapPin className="w-5 h-5" />,
    color: 'bg-green-500',
    examples: [
      'Locations & geography',
      'Factions & organizations',
      'Countries & kingdoms',
      'Schools & sects'
    ],
    examplesCn: [
      '地點與地理',
      '勢力與組織',
      '國家與王國',
      '學院與門派'
    ],
    description: 'Where things happen and who controls what',
    descriptionCn: '故事發生的地點和勢力分佈',
    backendCategories: ['location', 'faction', 'organization', 'place', 'geography']
  },
  {
    id: 'rules',
    label: 'World Rules',
    labelCn: '世界規則',
    icon: <Scale className="w-5 h-5" />,
    color: 'bg-red-500',
    examples: [
      '"Magic costs life force"',
      '"Vampires cannot enter without invitation"',
      '"Cultivation requires spiritual roots"',
      '"Time travel creates paradoxes"'
    ],
    examplesCn: [
      '"魔法消耗生命力"',
      '"吸血鬼不能不請自入"',
      '"修煉需要靈根"',
      '"時間旅行會產生悖論"'
    ],
    description: 'The unchanging laws of your universe',
    descriptionCn: '你世界中不可違背的法則',
    backendCategories: ['world_rule', 'rule', 'law', 'constraint']
  },
  {
    id: 'lore',
    label: 'Lore & History',
    labelCn: '傳說與歷史',
    icon: <BookOpen className="w-5 h-5" />,
    color: 'bg-blue-500',
    examples: [
      'Historical events',
      'Myths & legends',
      'Prophecies',
      'Artifacts & relics',
      'Important concepts'
    ],
    examplesCn: [
      '歷史事件',
      '神話傳說',
      '預言',
      '神器與遺物',
      '重要概念'
    ],
    description: 'The backstory and mysteries of your world',
    descriptionCn: '你世界的背景故事和謎團',
    backendCategories: ['lore', 'history', 'event', 'artifact', 'concept', 'world_concept', 'term', 'mystery']
  }
]

interface KnowledgeCategoryPickerProps {
  selected?: string
  onSelect: (category: SimplifiedCategory) => void
  language?: 'en' | 'zh-TW'
}

export function KnowledgeCategoryPicker({ 
  selected, 
  onSelect,
  language = 'en'
}: KnowledgeCategoryPickerProps) {
  const isZh = language === 'zh-TW'
  
  return (
    <div className="space-y-3">
      <div className="text-sm text-gray-400 flex items-center gap-2">
        <HelpCircle className="w-4 h-4" />
        {isZh ? '這是什麼類型的資訊？' : 'What type of information is this?'}
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {SIMPLIFIED_CATEGORIES.map(category => (
          <button
            key={category.id}
            onClick={() => onSelect(category)}
            className={`
              p-4 rounded-lg border-2 transition-all text-left
              ${selected === category.id 
                ? 'border-white bg-gray-800' 
                : 'border-gray-700 hover:border-gray-500 bg-gray-900'
              }
            `}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className={`p-2 rounded-lg ${category.color}`}>
                {category.icon}
              </div>
              <div>
                <div className="font-semibold text-white">
                  {isZh ? category.labelCn : category.label}
                </div>
                <div className="text-xs text-gray-400">
                  {isZh ? category.descriptionCn : category.description}
                </div>
              </div>
            </div>
            
            <div className="mt-3 space-y-1">
              <div className="text-xs text-gray-500 uppercase tracking-wide">
                {isZh ? '例如：' : 'Examples:'}
              </div>
              <div className="flex flex-wrap gap-1">
                {(isZh ? category.examplesCn : category.examples).slice(0, 3).map((example, i) => (
                  <span 
                    key={i}
                    className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded"
                  >
                    {example}
                  </span>
                ))}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// Helper to map simplified category to backend category
export function getBackendCategory(simplifiedCategoryId: string, content: string): string {
  const category = SIMPLIFIED_CATEGORIES.find(c => c.id === simplifiedCategoryId)
  if (!category) return 'general'
  
  // Return the first/primary backend category
  return category.backendCategories[0]
}
