interface Props {
  score: number          // 0–100
  sourceDiversity: number
  earliness: number
}

function strengthLabel(score: number) {
  if (score >= 70) return { text: 'Strong signal',   color: 'text-emerald-400' }
  if (score >= 45) return { text: 'Building signal', color: 'text-amber-400'   }
  if (score >= 20) return { text: 'Weak signal',     color: 'text-slate-400'   }
  return               { text: 'Detected',           color: 'text-slate-500'   }
}

function earlinessLabel(e: number) {
  if (e >= 0.7) return 'Still early — ahead of mainstream'
  if (e >= 0.4) return 'Building wider awareness'
  return 'Well-covered in mainstream media'
}

export function SignalMeter({ score, sourceDiversity, earliness }: Props) {
  const { text, color } = strengthLabel(score)
  const pct = Math.round(score)

  return (
    <div className="space-y-3">
      {/* Bar */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className={`text-sm font-medium ${color}`}>{text}</span>
          <span className="text-[11px] text-text-secondary">
            {sourceDiversity} independent source{sourceDiversity !== 1 ? 's' : ''} confirming
          </span>
        </div>
        <div className="h-2 rounded-full bg-surface-border overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${pct}%`,
              background: score >= 70
                ? 'linear-gradient(90deg, #00b37a, #00e5a0)'
                : score >= 45
                ? 'linear-gradient(90deg, #c07800, #f0a500)'
                : 'linear-gradient(90deg, #444c56, #8b949e)',
            }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-muted">
          <span>Weak</span><span>Strong</span>
        </div>
      </div>

      {/* Timing note */}
      <p className="text-xs text-text-secondary">{earlinessLabel(earliness)}</p>
    </div>
  )
}
