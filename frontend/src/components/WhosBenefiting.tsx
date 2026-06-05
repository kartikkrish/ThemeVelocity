import type { BeneficiaryNode } from '../api/client'

const TIERS: Record<string, { label: string; sub: string; accent: string }> = {
  direct:      { label: 'At the Center',    sub: 'Companies whose core business revolves around this theme',      accent: 'border-emerald-400/30 bg-emerald-400/5'  },
  first_order: { label: 'Key Suppliers',    sub: 'Companies that make critical parts for the direct players',    accent: 'border-sky-400/30    bg-sky-400/5'        },
  second_order: { label: 'Component Makers', sub: 'Less obvious suppliers — the layer behind the key suppliers', accent: 'border-violet-400/30  bg-violet-400/5'    },
  proxy:       { label: 'Indirect Plays',   sub: 'Thematic connection — less direct, more speculative',          accent: 'border-slate-400/30  bg-slate-400/5'     },
}

const LINKAGE: Record<string, { dot: string; label: string }> = {
  tight:    { dot: 'bg-emerald-400', label: 'Strong link'   },
  moderate: { dot: 'bg-amber-400',   label: 'Some exposure' },
  loose:    { dot: 'bg-slate-500',   label: 'Speculative'   },
}

const EXCHANGE_COLOR: Record<string, string> = {
  NYSE:    'text-sky-400',
  NASDAQ:  'text-sky-400',
  NSE:     'text-orange-400',
  BSE:     'text-orange-400',
  OTC:     'text-slate-500',
}

function NodeCard({ node }: { node: BeneficiaryNode }) {
  const lk = LINKAGE[node.linkage_tightness] ?? LINKAGE['loose']
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
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${lk.dot}`} />
        <span className="text-[10px] text-muted">{lk.label}</span>
        {node.exchange && (
          <span className={`text-[10px] ml-auto ${exColor}`}>{node.exchange}</span>
        )}
      </div>
    </div>
  )
}

interface Props {
  nodes: BeneficiaryNode[]
}

export function WhosBenefiting({ nodes }: Props) {
  const roleOrder = ['direct', 'first_order', 'second_order', 'proxy']
  const byRole = roleOrder.reduce((acc, role) => {
    acc[role] = nodes.filter(n => n.node_role === role)
    return acc
  }, {} as Record<string, BeneficiaryNode[]>)

  const activeTiers = roleOrder.filter(r => byRole[r].length > 0)

  if (activeTiers.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted">
        Value-chain analysis not yet available for this theme.
        <br />
        <span className="text-[11px]">It runs automatically when the theme reaches a strong signal.</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {activeTiers.map(role => {
        const tier = TIERS[role]
        return (
          <div key={role}>
            <div className="mb-2">
              <p className="text-sm font-semibold text-text-primary">{tier.label}</p>
              <p className="text-[11px] text-muted">{tier.sub}</p>
            </div>
            <div className={`grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 p-3 rounded-xl border ${tier.accent}`}>
              {byRole[role].map((n, i) => <NodeCard key={i} node={n} />)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
