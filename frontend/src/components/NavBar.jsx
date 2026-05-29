import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Home' },
  { to: '/recommend', label: 'Crop Advisor' },
  { to: '/profit', label: 'Profit Planner' },
  { to: '/mandi', label: 'Mandi Compare' },
  { to: '/map', label: 'State Map' },
  { to: '/crops', label: 'Crop Analyser' },
  { to: '/trends', label: 'Price Trend' },
  { to: '/revenue', label: 'Revenue Loss' },
  { to: '/forecast', label: 'Forecast' },
]

export default function NavBar() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)

  return (
    <nav className="bg-green-800 text-white px-4 md:px-6 py-3 text-sm font-medium">
      <div className="flex items-center justify-between">
        <span className="font-bold text-green-200">🌾 Agri Market Analyser</span>
        <button className="md:hidden text-2xl leading-none" onClick={() => setOpen(!open)}
          aria-label="Toggle menu">{open ? '✕' : '☰'}</button>
        <div className="hidden md:flex gap-5">
          {links.map((l) => (
            <Link key={l.to} to={l.to}
              className={pathname === l.to ? 'text-yellow-300' : 'hover:text-green-200'}>
              {l.label}
            </Link>
          ))}
        </div>
      </div>
      {open && (
        <div className="md:hidden flex flex-col gap-1 mt-3 pb-1">
          {links.map((l) => (
            <Link key={l.to} to={l.to} onClick={() => setOpen(false)}
              className={`py-2 px-1 border-b border-green-700 ${pathname === l.to ? 'text-yellow-300' : 'hover:text-green-200'}`}>
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  )
}
