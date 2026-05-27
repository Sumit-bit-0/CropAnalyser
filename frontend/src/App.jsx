import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar'
import StateMap from './pages/StateMap'
import CropAnalyser from './pages/CropAnalyser'
import PriceTrend from './pages/PriceTrend'
import RevenueLoss from './pages/RevenueLoss'
import Forecast from './pages/Forecast'

export default function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <main className="p-6">
        <Routes>
          <Route path="/"         element={<StateMap />} />
          <Route path="/crops"    element={<CropAnalyser />} />
          <Route path="/trends"   element={<PriceTrend />} />
          <Route path="/revenue"  element={<RevenueLoss />} />
          <Route path="/forecast" element={<Forecast />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
