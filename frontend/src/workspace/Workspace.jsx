import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'
import { Sprout, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getTrendFilters } from '../api/client'
import { useWorkspace } from './WorkspaceContext'
import ContextBar from './ContextBar'
import ModeToggle from './ModeToggle'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import CropAdvisor from '../pages/CropAdvisor'
import CropRecommender from '../pages/CropRecommender'
import MandiCompare from '../pages/MandiCompare'
import ProfitPlanner from '../pages/ProfitPlanner'
import FpoBulkDashboard from '../pages/FpoBulkDashboard'
import StateMap from '../pages/StateMap'
import CropAnalyser from '../pages/CropAnalyser'
import RevenueLoss from '../pages/RevenueLoss'
import PriceTrend from '../pages/PriceTrend'
import Forecast from '../pages/Forecast'

const INTENTS = [
  { id: 'grow', emoji: '🌱', labelKey: 'ws.intent.grow', tools: [
    { id: 'advisor', labelKey: 'ws.tool.advisor', C: CropAdvisor },
    { id: 'soil', labelKey: 'ws.tool.soil', C: CropRecommender },
  ] },
  { id: 'sell', emoji: '💰', labelKey: 'ws.intent.sell', tools: [
    { id: 'mandi', labelKey: 'ws.tool.mandi', C: MandiCompare },
    { id: 'profit', labelKey: 'ws.tool.profit', C: ProfitPlanner },
    { id: 'fpo', labelKey: 'ws.tool.fpo', C: FpoBulkDashboard },
  ] },
  { id: 'explore', emoji: '📊', labelKey: 'ws.intent.explore', tools: [
    { id: 'map', labelKey: 'ws.tool.map', C: StateMap },
    { id: 'crops', labelKey: 'ws.tool.crops', C: CropAnalyser },
    { id: 'revenue', labelKey: 'ws.tool.revenue', C: RevenueLoss },
    { id: 'trends', labelKey: 'ws.tool.trends', C: PriceTrend },
    { id: 'forecast', labelKey: 'ws.tool.forecast', C: Forecast },
  ] },
]

// Tools whose output actually changes in Smart mode (soil-aware fusion).
const SMART_AFFECTS = new Set(['advisor', 'soil'])

export default function Workspace({ initialIntent = 'grow', initialTool = null }) {
  const { t } = useTranslation()
  const { mode } = useWorkspace()
  const [states, setStates] = useState([])
  const [intentId, setIntentId] = useState(initialIntent)
  const intent = INTENTS.find((i) => i.id === intentId) || INTENTS[0]
  const [toolId, setToolId] = useState(initialTool || intent.tools[0].id)

  useEffect(() => { getTrendFilters().then((d) => setStates(d.states)).catch(() => {}) }, [])

  const pickIntent = (id) => {
    setIntentId(id)
    setToolId(INTENTS.find((i) => i.id === id).tools[0].id)
  }
  const tool = intent.tools.find((t) => t.id === toolId) || intent.tools[0]
  const Tool = tool.C
  const smartAffects = SMART_AFFECTS.has(toolId)

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto max-w-[1100px] px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Sprout className="h-6 w-6 text-primary" />
            <span className="font-display font-semibold text-lg text-foreground">Crop Analyser</span>
          </Link>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <ModeToggle />
          </div>
        </div>
      </header>

      <ContextBar states={states} />

      <div className="border-b border-border">
        <div className="mx-auto max-w-[1100px] px-6">
          <nav className="flex gap-1 flex-wrap" aria-label="Workspace intent">
            {INTENTS.map((i) => (
              <button key={i.id} onClick={() => pickIntent(i.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                  i.id === intentId
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
                )}>
                <span>{i.emoji}</span>
                <span>{t(i.labelKey)}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div className="bg-secondary/40 border-b border-border">
        <div className="mx-auto max-w-[1100px] px-6">
          <div className="flex gap-1 flex-wrap py-1.5">
            {intent.tools.map((tl) => (
              <button key={tl.id} onClick={() => setToolId(tl.id)}
                className={cn(
                  'px-3 py-1.5 text-sm rounded-md transition-colors',
                  tl.id === toolId
                    ? 'bg-card text-primary font-medium shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}>
                {t(tl.labelKey)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {mode === 'smart' && (
          <motion.div key={smartAffects ? 'affects' : 'noop'}
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className={cn('overflow-hidden border-b border-border', smartAffects ? 'bg-primary/5' : 'bg-secondary/50')}>
            <div className="mx-auto max-w-[1100px] px-6 py-2.5 flex items-center gap-2 text-sm">
              <Sparkles className={cn('h-4 w-4 shrink-0', smartAffects ? 'text-primary' : 'text-muted-foreground')} />
              {smartAffects ? (
                <span className="text-foreground">
                  <b className="text-primary">{t('ws.smart.title')}</b> {t('ws.smart.affectsBody')}
                </span>
              ) : (
                <span className="text-muted-foreground">
                  <b className="text-foreground">{t('ws.smart.title')}.</b> {t('ws.smart.noopBody')}
                </span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="flex-1 py-8">
        <div className="mx-auto max-w-[1100px] px-6"><Tool /></div>
      </main>
    </div>
  )
}
