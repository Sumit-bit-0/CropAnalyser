import { Link } from 'react-router-dom'

const TOOLS = [
  { to: '/recommend', icon: '🌱', title: 'Crop Advisor', desc: 'Find the best crops for your soil & climate.' },
  { to: '/profit', icon: '💰', title: 'Profit Planner', desc: 'Estimate profit, break-even & selling risk.' },
  { to: '/mandi', icon: '📍', title: 'Mandi Compare', desc: 'Compare nearby markets & net price after transport.' },
  { to: '/map', icon: '🗺️', title: 'State Map', desc: 'Farm-to-retail price gaps across India.' },
  { to: '/trends', icon: '📈', title: 'Price Trend', desc: 'How a crop\'s price moved over time.' },
  { to: '/forecast', icon: '🔮', title: 'Forecast', desc: 'Predicted price for the months ahead.' },
]

export default function Home() {
  return (
    <div className="max-w-4xl w-full">
      <h1 className="text-2xl md:text-3xl font-bold text-green-800 mb-1">Your crop market companion</h1>
      <p className="text-gray-600 mb-6">Decide what to grow, where to sell, and when — in plain language.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOOLS.map((t) => (
          <Link key={t.to} to={t.to}
            className="block rounded-xl border border-gray-200 p-5 hover:border-green-500 hover:shadow-md transition bg-white">
            <div className="text-3xl mb-2">{t.icon}</div>
            <div className="font-semibold text-green-800 text-lg">{t.title}</div>
            <p className="text-sm text-gray-600 mt-1">{t.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
