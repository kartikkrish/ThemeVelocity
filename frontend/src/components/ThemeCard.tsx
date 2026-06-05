import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ThemeHeat } from '../api/client'
import { VelocitySparkline } from './VelocitySparkline'
import { MaturityBadge } from './MaturityBadge'

interface Props {
  theme: ThemeHeat
  rank: number
}

const CATALYST_SHORT: Record<string, string> = {
  earnings_guidance: 'Earnings catalyst',
  order_flow:        'Order activity',
  product_launch:    'Product launch',
  regulatory_change: 'Regulatory shift',
  tech_breakthrough: 'Tech breakthrough',
  macro_shift:       'Macro shift',
  pure_narrative:    'Narrative-driven',
}

function SourceDots({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < count ? 'bg-accent' : 'bg-surface-border'}`}
        />
      ))}
      <span className="text-[10px] text-muted ml-1">
        {count} source{count !== 1 ? 's' : ''}
      </span>
    </div>
  )
}

export function ThemeCard({ theme, rank }: Props) {
  const nav = useNavigate()
  const { data: detail } = useQuery({
    queryKey: ['theme', theme.theme_id],
    queryFn: () => api.getTheme(theme.theme_id),
    staleTime: 120_000,
  })

  const history = detail?.velocity_history ?? []
  const hasThesis = !!theme.one_line_thesis

  return (
    <div
      onClick={() => nav(`/theme/${theme.theme_id}`)}
      className="card p-4 cursor-pointer hover:border-accent/30 transition-all duration-200 hover:bg-surface-hover animate-fade-up"
      style={{ animationDelay: `${rank * 60}ms`, animationFillMode: 'both' }}
    >
      {/* Top row: rank + badges */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] text-muted font-tabular shrink-0">#{rank + 1}</span>
          {theme.maturity_stage
            ? <MaturityBadge stage={theme.maturity_stage} />
            : theme.breaching && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20 font-medium animate-pulse-accent">
                New signal
              </span>
            )
          }
        </div>
        {theme.catalyst_type && (
          <span className="text-[10px] text-text-secondary shrink-0">
            {CATALYST_SHORT[theme.catalyst_type] ?? theme.catalyst_type}
          </span>
        )}
      </div>

      {/* Theme name */}
      <h3 className="text-sm font-semibold text-text-primary mb-1.5">{theme.name}</h3>

      {/* Thesis — the hook */}
      {hasThesis ? (
        <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-2">
          {theme.one_line_thesis}
        </p>
      ) : (
        <p className="text-xs text-muted italic mb-3">Analysis in progress…</p>
      )}

      {/* Sparkline */}
      <div className="mb-3 -mx-1">
        <VelocitySparkline data={history} height={32} />
      </div>

      {/* Footer: sources + arrow */}
      <div className="flex items-center justify-between">
        <SourceDots count={theme.source_diversity} />
        <div className="flex items-center gap-1.5">
          {theme.earliness >= 0.7 && (
            <span className="text-[10px] text-emerald-400">Early stage</span>
          )}
          <svg className="w-3.5 h-3.5 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </div>
  )
}
