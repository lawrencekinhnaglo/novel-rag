import { useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Settings, Server, Database, Brain, 
  Globe, Thermometer, Check, RefreshCw,
  Languages, Layers
} from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { useSettingsStore, KNOWLEDGE_CATEGORIES } from '@/store/settingsStore'
import { languages, t } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export function SettingsPage() {
  const {
    provider, setProvider,
    temperature, setTemperature,
    useRag, setUseRag,
    useWebSearch, setUseWebSearch,
    includeGraph, setIncludeGraph
  } = useChatStore()

  const {
    language, setLanguage,
    maxContextTokens, setMaxContextTokens,
    activeCategories, toggleCategory,
    characterAwareness, setCharacterAwareness
  } = useSettingsStore()

  const [testStatus, setTestStatus] = useState<Record<string, 'idle' | 'testing' | 'success' | 'error'>>({
    lm_studio: 'idle',
    deepseek: 'idle',
    postgres: 'idle',
    neo4j: 'idle',
    redis: 'idle',
    qdrant: 'idle'
  })

  const testConnection = async (service: string) => {
    setTestStatus(prev => ({ ...prev, [service]: 'testing' }))
    
    // Simulate connection test
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // For demo, randomly succeed/fail
    const success = Math.random() > 0.3
    setTestStatus(prev => ({ ...prev, [service]: success ? 'success' : 'error' }))
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-display font-semibold text-foreground flex items-center gap-3">
            <Settings className="w-6 h-6 text-primary" />
            Settings
          </h1>
          <p className="text-muted-foreground mt-1">
            Configure your Novel RAG assistant
          </p>
        </div>

        {/* LLM Settings */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            LLM Provider
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <motion.button
              whileHover={{ scale: 1.02 }}
              onClick={() => setProvider('lm_studio')}
              className={cn(
                "p-4 rounded-xl border text-left transition-colors",
                provider === 'lm_studio'
                  ? "bg-primary/10 border-primary"
                  : "bg-card border-border hover:border-primary/50"
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-foreground">LM Studio</span>
                {provider === 'lm_studio' && (
                  <Check className="w-4 h-4 text-primary" />
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                Local LLM (Llama 4 Maverick)
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                http://localhost:1234/v1
              </p>
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              onClick={() => setProvider('deepseek')}
              className={cn(
                "p-4 rounded-xl border text-left transition-colors",
                provider === 'deepseek'
                  ? "bg-primary/10 border-primary"
                  : "bg-card border-border hover:border-primary/50"
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-foreground">DeepSeek</span>
                {provider === 'deepseek' && (
                  <Check className="w-4 h-4 text-primary" />
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                DeepSeek API
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Requires API key in .env
              </p>
            </motion.button>
          </div>
        </section>

        {/* Temperature */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Thermometer className="w-5 h-5 text-accent" />
            Temperature: {temperature.toFixed(1)}
          </h2>
          <div className="p-4 rounded-xl bg-card border border-border">
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-2">
              <span>More Focused (0)</span>
              <span>Balanced (0.7)</span>
              <span>More Creative (2)</span>
            </div>
          </div>
        </section>

        {/* RAG Settings */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-green-400" />
            RAG Settings
          </h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between p-4 rounded-xl bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors">
              <div>
                <span className="font-medium text-foreground">Enable RAG</span>
                <p className="text-sm text-muted-foreground">
                  Search chapters, knowledge base, and ideas for context
                </p>
              </div>
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="w-5 h-5 accent-primary rounded"
              />
            </label>

            <label className="flex items-center justify-between p-4 rounded-xl bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors">
              <div>
                <span className="font-medium text-foreground">Include Story Graph</span>
                <p className="text-sm text-muted-foreground">
                  Include character relationships and timeline from Neo4j
                </p>
              </div>
              <input
                type="checkbox"
                checked={includeGraph}
                onChange={(e) => setIncludeGraph(e.target.checked)}
                className="w-5 h-5 accent-primary rounded"
              />
            </label>

            <label className="flex items-center justify-between p-4 rounded-xl bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-blue-400" />
                <div>
                  <span className="font-medium text-foreground">Web Search</span>
                  <p className="text-sm text-muted-foreground">
                    Search the internet for additional context
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={useWebSearch}
                onChange={(e) => setUseWebSearch(e.target.checked)}
                className="w-5 h-5 accent-primary rounded"
              />
            </label>
          </div>
        </section>

        {/* Connection Status */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" />
            Service Status
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {[
              { id: 'lm_studio', name: 'LM Studio', port: '1234' },
              { id: 'postgres', name: 'PostgreSQL + pgvector', port: '5432' },
              { id: 'neo4j', name: 'Neo4j', port: '7474' },
              { id: 'redis', name: 'Redis', port: '6379' },
              { id: 'qdrant', name: 'Qdrant', port: '6333' },
            ].map((service) => (
              <div
                key={service.id}
                className="flex items-center justify-between p-4 rounded-xl bg-card border border-border"
              >
                <div>
                  <span className="font-medium text-foreground">{service.name}</span>
                  <p className="text-xs text-muted-foreground">Port: {service.port}</p>
                </div>
                <button
                  onClick={() => testConnection(service.id)}
                  disabled={testStatus[service.id] === 'testing'}
                  className={cn(
                    "flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-colors",
                    testStatus[service.id] === 'idle' && "bg-muted text-muted-foreground hover:bg-muted/80",
                    testStatus[service.id] === 'testing' && "bg-primary/20 text-primary",
                    testStatus[service.id] === 'success' && "bg-green-500/20 text-green-400",
                    testStatus[service.id] === 'error' && "bg-destructive/20 text-destructive"
                  )}
                >
                  {testStatus[service.id] === 'testing' ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      Testing...
                    </>
                  ) : testStatus[service.id] === 'success' ? (
                    <>
                      <Check className="w-3 h-3" />
                      Connected
                    </>
                  ) : testStatus[service.id] === 'error' ? (
                    'Failed'
                  ) : (
                    'Test'
                  )}
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* Language Settings */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Languages className="w-5 h-5 text-purple-400" />
            {t('settings.language', language)}
          </h2>
          <div className="grid gap-3 md:grid-cols-3">
            {languages.map((lang) => (
              <motion.button
                key={lang.code}
                whileHover={{ scale: 1.02 }}
                onClick={() => setLanguage(lang.code)}
                className={cn(
                  "p-4 rounded-xl border text-left transition-colors",
                  language === lang.code
                    ? "bg-primary/10 border-primary"
                    : "bg-card border-border hover:border-primary/50"
                )}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-foreground">{lang.nativeName}</span>
                    <p className="text-xs text-muted-foreground">{lang.name}</p>
                  </div>
                  {language === lang.code && (
                    <Check className="w-4 h-4 text-primary" />
                  )}
                </div>
              </motion.button>
            ))}
          </div>
        </section>

        {/* Context Settings */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4 flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            {t('settings.context_settings', language)}
          </h2>
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-card border border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-foreground">{t('settings.max_context', language)}</span>
                <span className="text-primary font-mono">{maxContextTokens.toLocaleString()}</span>
              </div>
              <input
                type="range"
                min="8000"
                max="128000"
                step="4000"
                value={maxContextTokens}
                onChange={(e) => setMaxContextTokens(parseInt(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-2">
                <span>8K</span>
                <span>32K</span>
                <span>64K</span>
                <span>128K</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {t('settings.max_context_desc', language)}
              </p>
            </div>

            <label className="flex items-center justify-between p-4 rounded-xl bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors">
              <div>
                <span className="font-medium text-foreground">Character Behavior Awareness</span>
                <p className="text-sm text-muted-foreground">
                  LLM will fully understand how each character would behave
                </p>
              </div>
              <input
                type="checkbox"
                checked={characterAwareness}
                onChange={(e) => setCharacterAwareness(e.target.checked)}
                className="w-5 h-5 accent-primary rounded"
              />
            </label>
          </div>
        </section>

        {/* Knowledge Categories */}
        <section className="mb-8">
          <h2 className="text-lg font-display font-semibold text-foreground mb-4">
            Active Knowledge Categories
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            Select which categories to include in RAG queries
          </p>
          <div className="flex flex-wrap gap-2">
            {KNOWLEDGE_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => toggleCategory(cat)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  activeCategories.includes(cat)
                    ? "bg-primary/20 text-primary"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                {t(`knowledge.category.${cat}`, language)}
              </button>
            ))}
          </div>
        </section>

        {/* Docker Commands */}
        <section>
          <h2 className="text-lg font-display font-semibold text-foreground mb-4">
            Quick Commands
          </h2>
          <div className="p-4 rounded-xl bg-card border border-border">
            <p className="text-sm text-muted-foreground mb-3">
              Start all services with Docker:
            </p>
            <pre className="p-3 rounded-lg bg-muted text-sm font-mono overflow-x-auto">
              docker-compose up -d
            </pre>
            <p className="text-sm text-muted-foreground mt-4 mb-3">
              Stop all services:
            </p>
            <pre className="p-3 rounded-lg bg-muted text-sm font-mono overflow-x-auto">
              docker-compose down
            </pre>
          </div>
        </section>
      </div>
    </div>
  )
}

