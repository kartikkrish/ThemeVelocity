import type { ConfidenceData } from '../api/client'

const CATALYST_LABELS: Record<string, string> = {
  earnings_guidance:  'Earnings Guidance',
  order_flow:         'Order Activity',
  product_launch:     'Product Launch',
  regulatory_change:  'Regulatory Shift',
  tech_breakthrough:  'Tech Breakthrough',
  macro_shift:        'Macro Shift',
  pure_narrative:     'Narrative-Driven',
}

const EPIS_LABELS: Record<string, { label: string; color: string; tip: string }> = {
  V: { label: 'Verified',  color: 'text-sky-400   bg-sky-400/10',   tip: 'Backed by SEC filings or official announcements' },
  E: { label: 'Estimated', color: 'text-amber-400 bg-amber-400/10', tip: 'Based on analyst estimates or projections'       },
  I: { label: 'Inferred',  color: 'text-violet-400 bg-violet-400/10', tip: 'Inferred from narrative patterns and signals'  },
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <div className="h-1.5 rounded-full bg-surface-border overflow-hidden flex-1">
      <div
        className={`h-full rounded-full ${color} transition-all duration-500`}
        style={{ width: `${Math.round((value / max) * 100)}%` }}
      />
    </div>
  )
}

interface Props {
  confidence: ConfidenceData
  catalystType?: string
}

export function ConfidenceBreakdown({ confidence, catalystType }: Props) {
  const epis = EPIS_LABELS[confidence.epistemic_tag] ?? EPIS_LABELS['I']

  const indicators = [
    {
      label: 'Signal strength',
      value: confidence.c_velocity + confidence.c_source,
      max: 45,
      color: 'bg-emerald-400',
      tip: `Based on how fast conversation is accelerating and how many sources are picking it up`,
    },
    {
      label: 'How early',
      value: confidence.c_earliness,
      max: 15,
      color: 'bg-sky-400',
      tip: `How much specialist sources dominate vs mainstream media — higher means more informational edge`,
    },
    {
      label: 'Catalyst clarity',
      value: confidence.c_catalyst,
      max: 20,
      color: 'bg-amber-400',
      tip: catalystType ? `Catalyst: ${CATALYST_LABELS[catalystType] ?? catalystType}` : 'Clarity of the underlying business catalyst',
    },
    {
      label: 'Confidence total',
      value: confidence.c_total,
      max: 100,
      color: 'bg-accent',
      tip: 'Combined signal across all dimensions',
    },
  ]

  return (
    <div className="space-y-4">
      {indicators.map(ind => (
        <div key={ind.label}>
          <div className="flex items-center gap-3 mb-1.5">
            <span className="text-xs text-text-secondary w-32 shrink-0">{ind.label}</span>
            <Bar value={ind.value} max={ind.max} color={ind.color} />
            <span className="text-xs text-muted font-tabular w-8 text-right">
              {Math.round((ind.value / ind.max) * 100)}%
            </span>
          </div>
          <p className="text-[10px] text-muted pl-[136px]">{ind.tip}</p>
        </div>
      ))}

      {/* Epistemic tag */}
      <div className="pt-2 border-t border-surface-border flex items-center gap-2">
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${epis.color}`}>
          {epis.label}
        </span>
        <span className="text-[10px] text-muted">{epis.tip}</span>
      </div>
    </div>
  )
}
