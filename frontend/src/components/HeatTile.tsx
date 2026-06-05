import { useNavigate } from 'react-router-dom'
import type { ThemeHeat } from '../api/client'

interface Props {
  theme: ThemeHeat
  rank: number
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-velocity-high'
  if (score >= 40) return 'text-velocity-medium'
  return 'text-velocity-low'
}

function scoreBg(score: number, breaching: boolean): string {
  if (breaching) return 'bg-accent/10 border-accent/40 animate-pulse-accent'
  if (score >= 50) return 'bg-surface-raised border-surface-border'
  return 'bg-surface-raised border-surface-border opacity-80'
}

export function HeatTile({ theme, rank }: Props) {
  const nav = useNavigate()
  const sc = theme.composite_score

  return (
    <button
      onClick={() => nav(`/theme/${theme.theme_id}`)}
      className={`
        relative flex flex-col justify-between p-3 rounded-lg border cursor-pointer
        transition-all duration-200 hover:border-accent/60 hover:bg-surface-hover text-left
        min-w-[140px] h-[88px] shrink-0
        ${scoreBg(sc, theme.breaching)}
      `}
    >
      {theme.breaching && (
        <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-accent" />
      )}
      <div>
        <p className="text-[11px] text-muted leading-tight line-clamp-2">{theme.name}</p>
      </div>
      <div className="flex items-end justify-between">
        <span className={`font-tabular text-lg font-medium leading-none ${scoreColor(sc)}`}>
          {sc.toFixed(1)}
        </span>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[10px] text-muted tabular-nums">{theme.source_diversity}src</span>
          <span className="text-[10px] text-muted tabular-nums">
            {(theme.earliness * 100).toFixed(0)}% early
          </span>
        </div>
      </div>
    </button>
  )
}
