import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function Alerts() {
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(),
    refetchInterval: 30_000,
  })

  return (
    <div className="min-h-screen bg-surface px-4 py-4 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-base font-semibold text-text-primary">Alerts</h1>
        <span className="text-xs text-muted">{data.length} total</span>
      </div>

      {isError && <p className="text-sm text-red-400 mb-4">Could not load alerts.</p>}

      {isLoading && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-surface-border/30 animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && data.length === 0 && (
        <div className="py-16 text-center space-y-2">
          <p className="text-2xl">📡</p>
          <p className="text-sm font-medium text-text-secondary">No alerts yet</p>
          <p className="text-xs text-muted">Alerts fire when a theme reaches a strong signal threshold.</p>
        </div>
      )}

      <div className="space-y-2">
        {data.map(a => (
          <Link
            key={a.alert_id}
            to={`/theme/${a.theme_id}`}
            className="card p-4 flex gap-4 hover:border-accent/30 transition-all"
          >
            {/* Signal dot */}
            <div className="shrink-0 mt-1">
              <span className="block w-2 h-2 rounded-full bg-accent animate-pulse-accent" />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-3 mb-1">
                <p className="text-sm font-semibold text-text-primary truncate">
                  {a.theme_name || a.theme_id}
                </p>
                <span className="text-[11px] text-muted shrink-0">{timeAgo(a.fired_at)}</span>
              </div>
              {a.one_line_thesis ? (
                <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">
                  {a.one_line_thesis}
                </p>
              ) : (
                <p className="text-xs text-muted">Signal threshold crossed — tap to see details</p>
              )}
            </div>

            {/* Arrow */}
            <svg className="w-4 h-4 text-muted shrink-0 self-center" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        ))}
      </div>
    </div>
  )
}
