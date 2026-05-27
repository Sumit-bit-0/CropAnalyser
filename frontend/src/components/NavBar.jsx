import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'State Map' },
  { to: '/crops', label: 'Crop Analyser' },
  { to: '/trends', label: 'Price Trend' },
  { to: '/revenue', label: 'Revenue Loss' },
  { to: '/forecast', label: 'Forecast' },
]

export default function NavBar() {
  const { pathname } = useLocation()
  return (
    <nav className="bg-green-800 text-white px-6 py-3 flex gap-6 text-sm font-medium">
      <span className="font-bold text-green-200 mr-4">Agri Market Analyser</span>
      {links.map(l => (
        <Link key={l.to} to={l.to}
          className={pathname === l.to ? 'text-yellow-300' : 'hover:text-green-200'}>
          {l.label}
        </Link>
      ))}
    </nav>
  )
}
