const STAGES: Record<string, { label: string; icon: string; color: string; sub: string }> = {
  early_discovery:   { label: 'Early Discovery',  icon: '🔍', color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20', sub: "Specialists are talking. Mainstream hasn't noticed yet." },
  building_momentum: { label: 'Building Momentum', icon: '📈', color: 'text-amber-400  bg-amber-400/10  border-amber-400/20',   sub: 'Theme is accelerating and gaining wider attention.' },
  mainstream_known:  { label: 'Widely Covered',    icon: '📰', color: 'text-slate-400  bg-slate-400/10  border-slate-400/20',   sub: 'Well-known theme. Less informational edge.' },
}

interface Props {
  stage: string
  showSub?: boolean
}

export function MaturityBadge({ stage, showSub }: Props) {
  const s = STAGES[stage] ?? STAGES['building_momentum']
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium ${s.color}`}>
        <span>{s.icon}</span>{s.label}
      </span>
      {showSub && <p className="text-[11px] text-text-secondary pl-1">{s.sub}</p>}
    </div>
  )
}
