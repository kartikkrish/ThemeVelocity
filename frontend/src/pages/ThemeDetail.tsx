import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '../api/client'
import type { VelocityPoint } from '../api/client'
import { MaturityBadge } from '../components/MaturityBadge'
import { SignalMeter } from '../components/SignalMeter'
import { ConfidenceBreakdown } from '../components/ConfidenceBreakdown'
import { WhosBenefiting } from '../components/WhosBenefiting'
import { IndiaCrossmap } from '../components/IndiaCrossmap'
import { SignalTimeline } from '../components/SignalTimeline'

const CHART_COLORS = { line: '#00e5a0', grid: '#21262d', axis: '#8b949e' }

const CATALYST_LABELS: Record<string, { label: string; description: string }> = {
  earnings_guidance:  { label: 'Earnings Guidance',   description: 'Companies are raising guidance or flagging this theme in earnings calls' },
  order_flow:         { label: 'Order Activity',       description: 'Concrete orders or backlog expansion visible in filings' },
  product_launch:     { label: 'Product Launch',       description: 'New product or major upgrade announced by key players' },
  regulatory_change:  { label: 'Regulatory Shift',     description: 'Policy change or mandate creating structural demand' },
  tech_breakthrough:  { label: 'Tech Breakthrough',    description: "Meaningful technology advance shifting what's possible" },
  macro_shift:        { label: 'Macro Shift',          description: 'Broad economic or structural change creating tailwinds' },
  pure_narrative:     { label: 'Narrative-Driven',     description: 'Primarily conversation-driven — watch for hard catalyst confirmation' },
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-semibold text-text-primary mb-3">{children}</h2>
}

function AnalystRow({ label, value }: { label: string; value: string | number }) {
  return (
    <tr className="border-t border-surface-border">
      <td className="py-1.5 pr-4 text-[11px] text-muted w-28">{label}</td>
      <td className="py-1.5 font-tabular text-[11px] text-text-secondary">{value}</td>
    </tr>
  )
}

function PinButton({ themeId, name }: { themeId: string; name: string }) {
  const qc = useQueryClient()
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: api.getWatchlist, staleTime: 30_000 })
  const isPinned = wl.data?.some(w => w.theme_id === themeId) ?? false

  const toggle = useMutation({
    mutationFn: () => api.toggleWatchlist(themeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  return (
    <button
      onClick={e => { e.stopPropagation(); toggle.mutate() }}
      disabled={toggle.isPending}
      title={isPinned ? 'Remove from watchlist' : 'Add to watchlist'}
      className={`flex items-center gap-1.5 text-[11px] px-3 py-1 rounded-full border transition-colors disabled:opacity-50
        ${isPinned
          ? 'bg-accent/10 text-accent border-accent/20 hover:bg-red-400/10 hover:text-red-400 hover:border-red-400/20'
          : 'bg-surface-raised text-muted border-surface-border hover:bg-accent/10 hover:text-accent hover:border-accent/20'
        }`}
    >
      <svg className="w-3 h-3" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
      </svg>
      {isPinned ? 'Watching' : 'Watch'}
    </button>
  )
}

export function ThemeDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [analystOpen, setAnalystOpen] = useState(false)
  const [signalOpen, setSignalOpen] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['theme', id],
    queryFn: () => api.getTheme(id!),
    enabled: !!id,
    refetchInterval: 60_000,
  })

  const [llmNotice, setLlmNotice] = useState<string | null>(null)

  const analyze = useMutation({
    mutationFn: () => api.analyzeTheme(id!),
    onSuccess: (res) => {
      if (res.status === 'unavailable') { setLlmNotice(res.reason ?? 'Model unavailable.'); return }
      setLlmNotice(null)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['theme', id] }), 4000)
    },
  })

  const india = useMutation({
    mutationFn: () => api.triggerIndia(id!),
    onSuccess: (res: { status: string; reason?: string }) => {
      if (res.status === 'unavailable') { setLlmNotice(res.reason ?? 'Model unavailable.'); return }
      setLlmNotice(null)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['theme', id] }), 5000)
    },
  })

  if (isLoading) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-6 w-48 bg-surface-border/40 rounded animate-pulse" />
        <div className="h-20 rounded-xl bg-surface-border/30 animate-pulse" />
        <div className="h-48 rounded-xl bg-surface-border/20 animate-pulse" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-sm text-red-400">
        Failed to load. <Link to="/" className="underline text-accent">Back</Link>
      </div>
    )
  }

  const synthesis = data.synthesis
  const confidence = data.confidence
  const catalyst = synthesis ? (CATALYST_LABELS[synthesis.catalyst_type] ?? { label: synthesis.catalyst_type, description: '' }) : null

  const chartData = data.velocity_history.map((h: VelocityPoint) => ({
    ...h,
    day: new Date(h.ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className="min-h-screen bg-surface">
      <div className="px-4 py-4 max-w-4xl mx-auto space-y-4">

        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-muted">
          <Link to="/" className="hover:text-text-primary transition-colors">Dashboard</Link>
          <span>/</span>
          <span className="text-text-secondary truncate">{data.name}</span>
        </div>

        {/* ── Hero ── */}
        <div className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              {synthesis?.maturity_stage
                ? <MaturityBadge stage={synthesis.maturity_stage} showSub />
                : data.breaching && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20 font-medium animate-pulse-accent">
                    New signal
                  </span>
                )
              }
            </div>
            <PinButton themeId={data.theme_id} name={data.name} />
          </div>

          <h1 className="text-xl font-semibold text-text-primary mb-2">{data.name}</h1>

          {synthesis?.one_line_thesis ? (
            <p className="text-base text-text-secondary leading-relaxed mb-4">
              {synthesis.one_line_thesis}
            </p>
          ) : (
            <p className="text-sm text-muted italic mb-4">
              Theme synthesis is running — check back in a moment.
            </p>
          )}

          {/* Catalyst pill */}
          {catalyst && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-raised border border-surface-border">
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 shrink-0 mt-0.5">
                {catalyst.label}
              </span>
              {synthesis?.catalyst_low_confidence && (
                <span
                  title="Catalyst type classified by a small local model — treat as a guess, not a confirmed catalyst."
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-text-secondary/10 text-text-secondary border border-surface-border shrink-0 mt-0.5"
                >
                  low-confidence
                </span>
              )}
              <p className="text-xs text-text-secondary">{synthesis?.catalyst_detail || catalyst.description}</p>
            </div>
          )}
        </div>

        {/* ── Signal snapshot ── */}
        <div className="card p-5">
          <SectionTitle>Signal snapshot</SectionTitle>
          <SignalMeter
            score={data.composite_score}
            sourceDiversity={data.source_diversity}
            earliness={data.earliness}
          />
        </div>

        {/* ── How confident are we ── */}
        {confidence && (
          <div className="card p-5">
            <SectionTitle>How confident are we?</SectionTitle>
            <ConfidenceBreakdown
              confidence={confidence}
              catalystType={synthesis?.catalyst_type}
            />
          </div>
        )}

        {/* ── Who benefits ── */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <SectionTitle>Who benefits</SectionTitle>
            {!synthesis && (
              <button
                onClick={() => analyze.mutate()}
                disabled={analyze.isPending}
                className="text-[11px] px-3 py-1 rounded-full bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition-colors disabled:opacity-50"
              >
                {analyze.isPending ? 'Analyzing…' : 'Run analysis'}
              </button>
            )}
          </div>
          {llmNotice && (
            <div className="mb-3 text-[11px] px-3 py-2 rounded-lg bg-amber-400/10 text-amber-400 border border-amber-400/20">
              ⚠ {llmNotice} The velocity radar below works without it.
            </div>
          )}
          <WhosBenefiting nodes={data.beneficiaries} />
        </div>

        {/* ── India cross-map ── */}
        <div className="card p-5">
          <IndiaCrossmap
            nodes={data.india_crossmap ?? []}
            exposureRating={data.india_exposure_rating}
            onTrigger={() => india.mutate()}
            isPending={india.isPending}
          />
        </div>

        {/* ── Momentum chart ── */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <SectionTitle>Signal momentum over time</SectionTitle>
            <span className="text-[10px] text-muted">daily · last 90 days</span>
          </div>
          {chartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-sm text-muted">
              No history yet — run ingestion to populate.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
                <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} domain={[0, 100]}
                  tickFormatter={v => v === 0 ? '' : v === 100 ? 'Strong' : v === 50 ? 'Mid' : ''} />
                <Tooltip
                  contentStyle={{ background: '#161b22', border: '1px solid #21262d', borderRadius: 6, fontSize: 11, color: '#e6edf3' }}
                  formatter={(v: number) => [v.toFixed(0), 'Signal strength']}
                />
                <ReferenceLine y={50} stroke="#f0a500" strokeDasharray="4 4" strokeWidth={1}
                  label={{ value: 'Alert threshold', position: 'right', fontSize: 9, fill: '#f0a500' }} />
                <Line type="monotone" dataKey="composite_score" stroke={CHART_COLORS.line} strokeWidth={2}
                  dot={false} activeDot={{ r: 4, fill: CHART_COLORS.line, stroke: '#0d1117', strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ── Per-source signal timeline (collapsible) ── */}
        <div className="card overflow-hidden">
          <button
            onClick={() => setSignalOpen(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3 text-xs text-muted hover:text-text-secondary transition-colors"
          >
            <span className="font-medium">Per-source signal timeline</span>
            <svg className={`w-4 h-4 transition-transform ${signalOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {signalOpen && (
            <div className="px-5 pb-5 border-t border-surface-border pt-4">
              <p className="text-[10px] text-muted mb-4">
                Z-score per source over time. Z ≥ 2.0 (dashed line) indicates a structural break in mention rate.
              </p>
              <SignalTimeline themeId={data.theme_id} />
            </div>
          )}
        </div>

        {/* ── Analyst view (collapsed) ── */}
        <div className="card overflow-hidden">
          <button
            onClick={() => setAnalystOpen(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3 text-xs text-muted hover:text-text-secondary transition-colors"
          >
            <span className="font-medium">Analyst view — technical signals</span>
            <svg className={`w-4 h-4 transition-transform ${analystOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {analystOpen && (
            <div className="px-5 pb-5 border-t border-surface-border pt-4">
              <p className="text-[10px] text-muted mb-4">
                Raw statistical signals — Z-score ≥ 2.0 and CUSUM ≥ 4.0 indicate a structural break in mention rate for that source.
              </p>
              <table className="w-full text-left">
                <thead>
                  <tr>
                    {['Source', 'Z-Score', 'CUSUM', 'Velocity', 'Accel', '1d Mentions'].map(h => (
                      <th key={h} className="pb-2 pr-4 text-[10px] text-muted uppercase tracking-wider font-medium text-right first:text-left">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.per_source.map(s => {
                    const breach = s.zscore >= 2.0 || s.cusum >= 4.0
                    return (
                      <tr key={s.source} className="border-t border-surface-border">
                        <td className="py-2 pr-4">
                          <div className="flex items-center gap-2">
                            {breach && <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />}
                            <span className="text-xs text-text-primary font-medium uppercase">{s.source}</span>
                          </div>
                        </td>
                        <td className="py-2 pr-4 font-tabular text-xs text-right">
                          <span className={s.zscore >= 2 ? 'text-accent' : 'text-text-secondary'}>{s.zscore.toFixed(2)}</span>
                        </td>
                        <td className="py-2 pr-4 font-tabular text-xs text-right">
                          <span className={s.cusum >= 4 ? 'text-accent' : 'text-text-secondary'}>{s.cusum.toFixed(2)}</span>
                        </td>
                        <td className="py-2 pr-4 font-tabular text-xs text-right text-text-secondary">
                          {s.velocity >= 0 ? '+' : ''}{s.velocity.toFixed(1)}
                        </td>
                        <td className="py-2 pr-4 font-tabular text-xs text-right text-text-secondary">
                          {s.acceleration >= 0 ? '+' : ''}{s.acceleration.toFixed(2)}
                        </td>
                        <td className="py-2 font-tabular text-xs text-right text-text-secondary">{s.count_1d}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {/* Primitive */}
              {data.primitive && (
                <div className="mt-4 pt-3 border-t border-surface-border">
                  <p className="text-[10px] text-muted uppercase tracking-wider mb-1">Economic primitive</p>
                  <p className="text-xs text-text-secondary">{data.primitive}</p>
                </div>
              )}

              {/* Confidence breakdown numbers */}
              {confidence && (
                <div className="mt-4 pt-3 border-t border-surface-border">
                  <p className="text-[10px] text-muted uppercase tracking-wider mb-2">Confidence components</p>
                  <table className="w-full">
                    <tbody>
                      <AnalystRow label="Velocity (0–25)"   value={`${confidence.c_velocity} / 25`} />
                      <AnalystRow label="Source (0–20)"     value={`${confidence.c_source} / 20`}   />
                      <AnalystRow label="Catalyst (0–20)"   value={`${confidence.c_catalyst} / 20`} />
                      <AnalystRow label="Earliness (0–15)"  value={`${confidence.c_earliness} / 15`} />
                      <AnalystRow label="Linkage (0–10)"    value={`${confidence.c_linkage} / 10`}  />
                      <AnalystRow label="Liquidity (0–10)"  value={`${confidence.c_liquidity} / 10`} />
                      <AnalystRow label="Total"             value={`${confidence.c_total} / 100`}   />
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
