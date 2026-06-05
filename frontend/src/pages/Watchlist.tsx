import { useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { WatchlistItem } from '../api/client'
import { MaturityBadge } from '../components/MaturityBadge'

function ScorePill({ score }: { score: number }) {
  const color = score >= 70 ? 'text-accent' : score >= 40 ? 'text-amber-400' : 'text-muted'
  return <span className={`font-tabular text-sm font-semibold ${color}`}>{score.toFixed(0)}</span>
}

function WatchlistRow({ item, onUnpin }: { item: WatchlistItem; onUnpin: () => void }) {
  const nav = useNavigate()
  const ago = (() => {
    const d = Date.now() - new Date(item.pinned_at).getTime()
    const days = Math.floor(d / 86400000)
    if (days === 0) return 'Today'
    if (days === 1) return '1d ago'
    return `${days}d ago`
  })()

  return (
    <div
      className="card p-4 cursor-pointer hover:border-accent/30 transition-all duration-200 hover:bg-surface-hover"
      onClick={() => nav(`/theme/${item.theme_id}`)}
    >
      <div className="flex items-start gap-3">
        {/* Left: score */}
        <div className="flex flex-col items-center pt-0.5 min-w-[2.5rem]">
          <ScorePill score={item.composite_score} />
          <span className="text-[9px] text-muted mt-0.5">score</span>
        </div>

        {/* Middle: name + thesis */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="text-sm font-semibold text-text-primary">{item.name}</h3>
            {item.maturity_stage && <MaturityBadge stage={item.maturity_stage} />}
            {item.breaching && !item.maturity_stage && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20 animate-pulse-accent">
                Breaching
              </span>
            )}
          </div>
          {item.one_line_thesis ? (
            <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">{item.one_line_thesis}</p>
          ) : (
            <p className="text-xs text-muted italic">Analysis pending…</p>
          )}
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[10px] text-muted">{item.source_diversity} source{item.source_diversity !== 1 ? 's' : ''}</span>
            {item.earliness >= 0.7 && <span className="text-[10px] text-emerald-400">Early stage</span>}
            <span className="text-[10px] text-muted ml-auto">Pinned {ago}</span>
          </div>
        </div>

        {/* Right: unpin */}
        <button
          onClick={e => { e.stopPropagation(); onUnpin() }}
          title="Remove from watchlist"
          className="shrink-0 p-1.5 rounded-lg text-muted hover:text-red-400 hover:bg-red-400/10 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}

export function Watchlist() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: api.getWatchlist,
    refetchInterval: 60_000,
  })

  const unpin = useMutation({
    mutationFn: (id: string) => api.toggleWatchlist(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  return (
    <div className="min-h-screen bg-surface">
      <div className="px-4 py-4 max-w-3xl mx-auto space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Watchlist</h1>
            <p className="text-xs text-muted mt-0.5">
              Pinned themes — live velocity updates every minute
            </p>
          </div>
          {data && data.length > 0 && (
            <span className="text-xs text-muted">{data.length} theme{data.length !== 1 ? 's' : ''}</span>
          )}
        </div>

        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map(i => (
              <div key={i} className="h-24 rounded-xl bg-surface-border/20 animate-pulse" />
            ))}
          </div>
        )}

        {!isLoading && data?.length === 0 && (
          <div className="card p-10 text-center space-y-3">
            <div className="w-10 h-10 rounded-full bg-surface-raised border border-surface-border flex items-center justify-center mx-auto">
              <svg className="w-5 h-5 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
            </div>
            <p className="text-sm text-muted">No themes pinned yet.</p>
            <p className="text-xs text-muted">
              Open any theme and click <span className="text-text-secondary font-medium">Watch</span> to track it here.
            </p>
            <Link to="/" className="inline-block text-xs text-accent hover:underline mt-2">
              Browse themes
            </Link>
          </div>
        )}

        {data && data.length > 0 && (
          <div className="space-y-3">
            {data.map(item => (
              <WatchlistRow
                key={item.theme_id}
                item={item}
                onUnpin={() => unpin.mutate(item.theme_id)}
              />
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
