import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ThemeHeat } from '../api/client'
import { VelocitySparkline } from './VelocitySparkline'

interface Props {
  theme: ThemeHeat
  rank: number
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'HIGH'
  if (score >= 40) return 'MED'
  return 'LOW'
}

function scoreClass(score: number): string {
  if (score >= 70) return 'text-velocity-high bg-velocity-high/10'
  if (score >= 40) return 'text-velocity-medium bg-velocity-medium/10'
  return 'text-velocity-low bg-velocity-low/10'
}

export function ThemeCard({ theme, rank }: Props) {
  const nav = useNavigate()
  const { data: detail } = useQuery({
    queryKey: ['theme', theme.theme_id],
    queryFn: () => api.getTheme(theme.theme_id),
    staleTime: 120_000,
  })

  const history = detail?.velocity_history ?? []

  return (
    <div
      onClick={() => nav(`/theme/${theme.theme_id}`)}
      className="card p-4 cursor-pointer hover:border-accent/40 transition-all duration-200 hover:bg-surface-hover animate-fade-up"
      style={{ animationDelay: `${rank * 60}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-muted font-tabular shrink-0">#{rank + 1}</span>
          <h3 className="text-sm font-medium text-text-primary truncate">{theme.name}</h3>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {theme.breaching && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">
              BREACH
            </span>
          )}
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${scoreClass(theme.composite_score)}`}>
            {scoreLabel(theme.composite_score)}
          </span>
        </div>
      </div>

      {/* Sparkline */}
      <div className="mb-3 -mx-1">
        <VelocitySparkline data={history} height={36} />
      </div>

      {/* Metrics row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Score</p>
            <p className="font-tabular text-sm font-medium text-text-primary">
              {theme.composite_score.toFixed(1)}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Sources</p>
            <p className="font-tabular text-sm font-medium text-text-primary">
              {theme.source_diversity}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Earliness</p>
            <p className="font-tabular text-sm font-medium text-text-primary">
              {(theme.earliness * 100).toFixed(0)}%
            </p>
          </div>
        </div>
        <svg className="w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  )
}
