import { useEffect, useState } from 'react'
import { getTrendFilters } from '../api/client'
import { useWorkspace } from './WorkspaceContext'
import ContextBar from './ContextBar'
import ModeToggle from './ModeToggle'
import CropAdvisor from '../pages/CropAdvisor'
import CropRecommender from '../pages/CropRecommender'
import MandiCompare from '../pages/MandiCompare'
import ProfitPlanner from '../pages/ProfitPlanner'
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
    <div className="min-h-screen flex flex-col">
      <header className="bg-green-800 text-white px-4 md:px-6 py-3 flex items-center justify-between">
        <span className="font-bold text-green-200">🌾 Agri Market Analyser</span>
        <ModeToggle />
      </header>

      <ContextBar states={states} />

      <nav className="flex gap-2 px-4 md:px-6 pt-3 flex-wrap">
        {INTENTS.map((i) => (
          <button key={i.id} onClick={() => pickIntent(i.id)}
            className={`px-3 py-2 rounded-t-lg text-sm font-medium ${i.id === intentId ? 'bg-white border border-b-0 text-green-800' : 'bg-green-50 text-green-700 hover:bg-green-100'}`}>
            {i.label}
          </button>
        ))}
      </nav>
      <div className="flex gap-3 px-4 md:px-6 border-b text-sm">
        {intent.tools.map((t) => (
          <button key={t.id} onClick={() => setToolId(t.id)}
            className={`py-2 ${t.id === toolId ? 'text-green-800 font-semibold border-b-2 border-green-700' : 'text-gray-500 hover:text-green-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <main className="p-6 flex-1"><Tool /></main>
    </div>
  )
}
