import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Themes' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/settings', label: 'Settings' },
]

export function Nav() {
  const { pathname } = useLocation()
  return (
    <nav className="h-12 bg-surface-raised border-b border-surface-border flex items-center px-4 gap-6 sticky top-0 z-50">
      <Link to="/" className="flex items-center gap-2 mr-4 shrink-0">
        <span className="w-6 h-6 rounded bg-accent flex items-center justify-center">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <polyline points="1,10 4,6 7,8 10,3 13,5" stroke="#0d1117" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
        <span className="font-display font-semibold text-sm text-text-primary tracking-tight">
          Theme<span className="text-accent">Velocity</span>
        </span>
      </Link>
      {links.map(l => (
        <Link
          key={l.to}
          to={l.to}
          className={`text-sm font-medium transition-colors ${
            pathname === l.to
              ? 'text-text-primary'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          {l.label}
        </Link>
      ))}
      <div className="ml-auto flex items-center gap-2">
        <span className="inline-flex items-center gap-1 text-xs text-muted font-tabular">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Live
        </span>
      </div>
    </nav>
  )
}
