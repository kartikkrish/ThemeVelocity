import type { IndiaCrossmapNode } from '../api/client'

const TIERS: Record<string, { label: string; sub: string; accent: string }> = {
  direct:      { label: 'Direct Indian Play',    sub: 'Companies whose core business aligns with this theme',       accent: 'border-orange-400/30 bg-orange-400/5'  },
  first_order: { label: 'Key Supply Chain',       sub: 'Indian suppliers or enablers for the direct players',        accent: 'border-amber-400/30  bg-amber-400/5'   },
  second_order: { label: 'Indirect Exposure',     sub: 'Downstream or infrastructure companies with theme exposure', accent: 'border-violet-400/30  bg-violet-400/5' },
  proxy:       { label: 'Thematic Proxy',         sub: 'Loose thematic link — speculative at current information',   accent: 'border-slate-400/30  bg-slate-400/5'   },
}

const LINKAGE: Record<string, { dot: string; label: string }> = {
  tight:    { dot: 'bg-emerald-400', label: 'Strong link'   },
  moderate: { dot: 'bg-amber-400',   label: 'Some exposure' },
  loose:    { dot: 'bg-slate-500',   label: 'Speculative'   },
}

const LIQUIDITY: Record<string, { color: string; label: string }> = {
  ok:         { color: 'text-emerald-400', label: 'Liquid'      },
  sme:        { color: 'text-amber-400',   label: 'SME Board'   },
  illiquid:   { color: 'text-red-400',     label: 'Illiquid'    },
  unverified: { color: 'text-muted',       label: 'Unverified'  },
}

const EXCHANGE_COLOR: Record<string, string> = {
  NSE:  'text-orange-400',
  BSE:  'text-orange-400',
  SME:  'text-amber-400',
  NYSE: 'text-sky-400',
}

function IndiaNodeCard({ node }: { node: IndiaCrossmapNode }) {
  const lk = LINKAGE[node.linkage_tightness] ?? LINKAGE['loose']
  const liq = LIQUIDITY[node.liquidity_flag] ?? LIQUIDITY['unverified']
  const exColor = EXCHANGE_COLOR[node.exchange] ?? 'text-muted'

  return (
    <div className="bg-surface-raised border border-surface-border rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-text-primary leading-snug">{node.company_name}</p>
        {node.ticker && (
          <span className={`text-[11px] font-tabular font-semibold shrink-0 ${exColor}`}>
            {node.ticker}
          </span>
        )}
      </div>
      <p className="text-[11px] text-text-secondary leading-relaxed">{node.justification}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${lk.dot}`} />
          <span className="text-[10px] text-muted">{lk.label}</span>
        </div>
        <span className={`text-[10px] ${liq.color}`}>{liq.label}</span>
        {node.exchange && (
          <span className={`text-[10px] ml-auto ${exColor}`}>{node.exchange}</span>
        )}
      </div>
    </div>
  )
}

interface Props {
  nodes: IndiaCrossmapNode[]
  onTrigger?: () => void
  isPending?: boolean
  exposureRating?: string | null
}

export function IndiaCrossmap({ nodes, onTrigger, isPending, exposureRating }: Props) {
  const roleOrder = ['direct', 'first_order', 'second_order', 'proxy']
  const byRole = roleOrder.reduce((acc, role) => {
    acc[role] = nodes.filter(n => n.node_role === role)
    return acc
  }, {} as Record<string, IndiaCrossmapNode[]>)

  const activeTiers = roleOrder.filter(r => byRole[r].length > 0)

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">India cross-map</span>
          {exposureRating && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-400/10 text-orange-400 border border-orange-400/20 font-medium">
              {exposureRating}
            </span>
          )}
        </div>
        {onTrigger && (
          <button
            onClick={onTrigger}
            disabled={isPending}
            className="text-[11px] px-3 py-1 rounded-full bg-orange-400/10 text-orange-400 border border-orange-400/20 hover:bg-orange-400/20 transition-colors disabled:opacity-50"
          >
            {isPending ? 'Mapping…' : activeTiers.length > 0 ? 'Refresh' : 'Run India analysis'}
          </button>
        )}
      </div>

      <p className="text-[11px] text-muted">
        NSE / BSE / SME companies with economic exposure to this theme's underlying primitive.
      </p>

      {activeTiers.length === 0 ? (
        <div className="py-6 text-center text-sm text-muted">
          India cross-map not yet available.
          {onTrigger && (
            <span className="block text-[11px] mt-1">Run India analysis above to generate it.</span>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {activeTiers.map(role => {
            const tier = TIERS[role]
            return (
              <div key={role}>
                <div className="mb-2">
                  <p className="text-sm font-semibold text-text-primary">{tier.label}</p>
                  <p className="text-[11px] text-muted">{tier.sub}</p>
                </div>
                <div className={`grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 p-3 rounded-xl border ${tier.accent}`}>
                  {byRole[role].map((n, i) => <IndiaNodeCard key={i} node={n} />)}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
