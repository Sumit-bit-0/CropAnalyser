import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import StateMap from './pages/StateMap'
import CropAnalyser from './pages/CropAnalyser'
import PriceTrend from './pages/PriceTrend'
import RevenueLoss from './pages/RevenueLoss'
import Forecast from './pages/Forecast'
import CropRecommender from './pages/CropRecommender'
import CropAdvisor from './pages/CropAdvisor'
import ProfitPlanner from './pages/ProfitPlanner'
import MandiCompare from './pages/MandiCompare'

export default function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <main className="p-6">
        <Routes>
          <Route path="/"         element={<Home />} />
          <Route path="/map"      element={<StateMap />} />
          <Route path="/crops"    element={<CropAnalyser />} />
          <Route path="/trends"   element={<PriceTrend />} />
          <Route path="/revenue"  element={<RevenueLoss />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/advisor"  element={<CropAdvisor />} />
          <Route path="/recommend" element={<CropRecommender />} />
          <Route path="/profit"    element={<ProfitPlanner />} />
          <Route path="/mandi"     element={<MandiCompare />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
