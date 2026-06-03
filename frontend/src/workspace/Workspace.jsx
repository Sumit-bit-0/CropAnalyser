import { useEffect, useState } from 'react'
import { getTrendFilters } from '../api/client'
import { useWorkspace } from './WorkspaceContext'
import ContextBar from './ContextBar'
import ModeToggle from './ModeToggle'
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
  { id: 'grow', label: '🌱 What to grow', tools: [
    { id: 'advisor', label: 'Crop Advisor', C: CropAdvisor },
    { id: 'soil', label: 'Soil Match', C: CropRecommender },
  ] },
  { id: 'sell', label: '💰 Where & when to sell', tools: [
    { id: 'mandi', label: 'Mandi Compare', C: MandiCompare },
    { id: 'profit', label: 'Profit Planner', C: ProfitPlanner },
    { id: 'fpo', label: 'FPO Bulk Selling', C: FpoBulkDashboard },
  ] },
  { id: 'explore', label: '📊 Explore', tools: [
    { id: 'map', label: 'State Map', C: StateMap },
    { id: 'crops', label: 'Crop Analyser', C: CropAnalyser },
    { id: 'revenue', label: 'Revenue Loss', C: RevenueLoss },
    { id: 'trends', label: 'Price Trend', C: PriceTrend },
    { id: 'forecast', label: 'Forecast', C: Forecast },
  ] },
]

export default function Workspace({ initialIntent = 'grow', initialTool = null }) {
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

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="bg-primary text-primary-foreground px-4 md:px-6 py-3 flex items-center justify-between">
        <span className="font-bold">🌾 Agri Market Analyser</span>
        <ModeToggle />
      </header>

      <ContextBar states={states} />

      <nav className="flex gap-2 px-4 md:px-6 pt-3 flex-wrap">
        {INTENTS.map((i) => (
          <button key={i.id} onClick={() => pickIntent(i.id)}
            className={`px-3 py-2 rounded-t-lg text-sm font-medium transition-colors ${i.id === intentId ? 'bg-card border border-b-0 border-border text-primary' : 'bg-secondary text-secondary-foreground hover:bg-muted'}`}>
            {i.label}
          </button>
        ))}
      </nav>
      <div className="flex gap-3 px-4 md:px-6 border-b border-border text-sm">
        {intent.tools.map((t) => (
          <button key={t.id} onClick={() => setToolId(t.id)}
            className={`py-2 transition-colors ${t.id === toolId ? 'text-primary font-semibold border-b-2 border-primary' : 'text-muted-foreground hover:text-primary'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <main className="p-6 flex-1"><Tool /></main>
    </div>
  )
}
