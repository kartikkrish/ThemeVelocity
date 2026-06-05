import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export function Alerts() {
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(),
    refetchInterval: 30_000,
  })

  return (
    <div className="min-h-screen bg-surface px-4 py-4 max-w-3xl mx-auto">
      <h1 className="text-base font-semibold text-text-primary mb-4">Alerts</h1>
      {isError && <p className="text-sm text-red-400">Could not load alerts.</p>}
      {isLoading && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-surface-border/30 animate-pulse" />
          ))}
        </div>
      )}
      {!isLoading && data.length === 0 && (
        <div className="py-16 text-center text-muted text-sm">
          No alerts yet. Themes must breach threshold to fire.
        </div>
      )}
      <div className="space-y-2">
        {data.map(a => (
          <Link
            key={a.alert_id}
            to={`/theme/${a.theme_id}`}
            className="card p-3 flex items-center justify-between hover:border-accent/40 transition-all"
          >
            <div>
              <p className="text-sm font-medium text-text-primary">{a.theme_id}</p>
              <p className="text-xs text-muted">
                {new Date(a.fired_at).toLocaleString()}
              </p>
            </div>
            <div className="text-right">
              <p className="font-tabular text-sm text-accent">{a.composite_score.toFixed(1)}</p>
              {a.acknowledged && <p className="text-[10px] text-muted">ack'd</p>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
