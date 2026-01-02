import React, { useState } from 'react'
import { 
  X, 
  MessageSquare, 
  Globe, 
  PenTool, 
  ClipboardCheck,
  ArrowRight,
  Lightbulb,
  CheckCircle2
} from 'lucide-react'

interface QuickStartGuideProps {
  onClose: () => void
  language?: 'en' | 'zh-TW'
}

const STEPS = [
  {
    id: 1,
    title: 'Start with Chat',
    titleCn: '從對話開始',
    icon: MessageSquare,
    color: 'bg-blue-500',
    description: 'Tell the AI about your story idea. Brainstorm characters, plot, and world.',
    descriptionCn: '告訴AI你的故事構思。一起腦力激盪角色、情節和世界觀。',
    tips: [
      'Just talk naturally - no special format needed',
      'AI automatically detects your story series',
      'Like good responses to remember them'
    ],
    tipsCn: [
      '自然對話即可 - 不需要特殊格式',
      'AI會自動識別你的故事系列',
      '按讚好的回應來記住它們'
    ]
  },
  {
    id: 2,
    title: 'Build Your World',
    titleCn: '建構你的世界',
    icon: Globe,
    color: 'bg-green-500',
    description: 'Save important details about characters, powers, places, and rules.',
    descriptionCn: '保存角色、能力、地點和規則的重要細節。',
    tips: [
      '5 simple categories - no confusion',
      'One-click save from chat responses',
      'AI finds this info when you write'
    ],
    tipsCn: [
      '5個簡單分類 - 不再混亂',
      '從對話一鍵保存',
      '寫作時AI會自動查找這些資訊'
    ]
  },
  {
    id: 3,
    title: 'Write Chapters',
    titleCn: '撰寫章節',
    icon: PenTool,
    color: 'bg-purple-500',
    description: 'Create your story with AI assistance and automatic context.',
    descriptionCn: '在AI輔助和自動上下文下創作你的故事。',
    tips: [
      'AI knows your world while you write',
      'Save AI responses directly to chapters',
      'Track word count and progress'
    ],
    tipsCn: [
      '寫作時AI知道你的世界觀',
      '將AI回應直接保存到章節',
      '追蹤字數和進度'
    ]
  },
  {
    id: 4,
    title: 'Review & Verify',
    titleCn: '審核與驗證',
    icon: ClipboardCheck,
    color: 'bg-amber-500',
    description: 'Check AI extractions and ensure consistency.',
    descriptionCn: '檢查AI提取的內容並確保一致性。',
    tips: [
      'Approve or reject AI suggestions',
      'Check for plot holes',
      'Export when ready'
    ],
    tipsCn: [
      '批准或拒絕AI建議',
      '檢查劇情漏洞',
      '準備好後導出'
    ]
  }
]

export function QuickStartGuide({ onClose, language = 'en' }: QuickStartGuideProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const isZh = language === 'zh-TW'

  const step = STEPS[currentStep]
  const Icon = step.icon

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-2xl max-w-2xl w-full overflow-hidden border border-gray-700 shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Lightbulb className="w-6 h-6 text-yellow-400" />
            <h2 className="text-xl font-bold">
              {isZh ? '快速入門指南' : 'Quick Start Guide'}
            </h2>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-800 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-6 py-3 bg-gray-800/50 flex items-center gap-2">
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setCurrentStep(i)}
              className={`
                flex-1 h-2 rounded-full transition-all
                ${i <= currentStep ? 'bg-blue-500' : 'bg-gray-700'}
              `}
            />
          ))}
        </div>

        {/* Content */}
        <div className="p-8">
          <div className="flex items-start gap-6">
            <div className={`p-4 rounded-xl ${step.color}`}>
              <Icon className="w-8 h-8 text-white" />
            </div>
            
            <div className="flex-1">
              <div className="text-sm text-gray-400 mb-1">
                {isZh ? `步驟 ${step.id} / 4` : `Step ${step.id} of 4`}
              </div>
              <h3 className="text-2xl font-bold mb-3">
                {isZh ? step.titleCn : step.title}
              </h3>
              <p className="text-gray-300 text-lg mb-6">
                {isZh ? step.descriptionCn : step.description}
              </p>
              
              <div className="space-y-3">
                {(isZh ? step.tipsCn : step.tips).map((tip, i) => (
                  <div key={i} className="flex items-center gap-3 text-gray-400">
                    <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                    <span>{tip}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex items-center justify-between">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="px-4 py-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isZh ? '上一步' : 'Previous'}
          </button>
          
          {currentStep < STEPS.length - 1 ? (
            <button
              onClick={() => setCurrentStep(currentStep + 1)}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg flex items-center gap-2"
            >
              {isZh ? '下一步' : 'Next'}
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-6 py-2 bg-green-600 hover:bg-green-500 rounded-lg flex items-center gap-2"
            >
              {isZh ? '開始使用！' : 'Get Started!'}
              <CheckCircle2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Hook to manage first-time user experience
export function useQuickStart() {
  const [showGuide, setShowGuide] = useState(() => {
    const seen = localStorage.getItem('novel-rag-quickstart-seen')
    return !seen
  })

  const closeGuide = () => {
    setShowGuide(false)
    localStorage.setItem('novel-rag-quickstart-seen', 'true')
  }

  const resetGuide = () => {
    localStorage.removeItem('novel-rag-quickstart-seen')
    setShowGuide(true)
  }

  return { showGuide, closeGuide, resetGuide }
}
