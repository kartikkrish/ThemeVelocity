import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '../api/client'
import type { VelocityPoint } from '../api/client'

function StatCell({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-3">
      <p className="text-[10px] text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className="font-tabular text-xl font-medium text-text-primary">{value}</p>
      {sub && <p className="text-[10px] text-muted mt-0.5">{sub}</p>}
    </div>
  )
}

function SourceRow({
  source,
  zscore,
  cusum,
  velocity,
  acceleration,
  count_1d,
}: {
  source: string
  zscore: number
  cusum: number
  velocity: number
  acceleration: number
  count_1d: number
}) {
  const breaching = zscore >= 2.0 || cusum >= 4.0
  return (
    <tr className="border-t border-surface-border">
      <td className="py-2 pr-4">
        <div className="flex items-center gap-2">
          {breaching && <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />}
          <span className="text-sm text-text-primary font-medium uppercase">{source}</span>
        </div>
      </td>
      <td className="py-2 pr-4 font-tabular text-sm text-right">
        <span className={zscore >= 2 ? 'text-accent' : 'text-text-secondary'}>{zscore.toFixed(2)}</span>
      </td>
      <td className="py-2 pr-4 font-tabular text-sm text-right">
        <span className={cusum >= 4 ? 'text-accent' : 'text-text-secondary'}>{cusum.toFixed(2)}</span>
      </td>
      <td className="py-2 pr-4 font-tabular text-sm text-right text-text-secondary">
        {velocity >= 0 ? '+' : ''}{velocity.toFixed(1)}
      </td>
      <td className="py-2 pr-4 font-tabular text-sm text-right text-text-secondary">
        {acceleration >= 0 ? '+' : ''}{acceleration.toFixed(2)}
      </td>
      <td className="py-2 font-tabular text-sm text-right text-text-secondary">{count_1d}</td>
    </tr>
  )
}

const CHART_COLORS = {
  composite: '#00e5a0',
  grid: '#21262d',
  axis: '#8b949e',
}

export function ThemeDetail() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['theme', id],
    queryFn: () => api.getTheme(id!),
    enabled: !!id,
    refetchInterval: 60_000,
  })

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 bg-surface-border/40 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[...Array(4)].map((_, i) => <div key={i} className="h-20 rounded-lg bg-surface-border/30 animate-pulse" />)}
        </div>
        <div className="h-64 rounded-lg bg-surface-border/20 animate-pulse" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-red-400 text-sm">
        Failed to load theme. <Link to="/" className="underline text-accent">Back to dashboard</Link>
      </div>
    )
  }

  const history = data.velocity_history
  const chartData = history.map((h: VelocityPoint) => ({
    ...h,
    day: new Date(h.ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className="min-h-screen bg-surface">
      <div className="px-4 py-4 max-w-5xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-muted mb-4">
          <Link to="/" className="hover:text-text-primary transition-colors">Dashboard</Link>
          <span>/</span>
          <span className="text-text-secondary">{data.name}</span>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-semibold text-text-primary">{data.name}</h1>
              {data.breaching && (
                <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent font-medium animate-pulse-accent">
                  BREACHING
                </span>
              )}
              <span className="text-xs px-2 py-0.5 rounded bg-surface-border text-muted">
                {data.status}
              </span>
            </div>
            {data.primitive && (
              <p className="text-xs text-muted max-w-xl">{data.primitive}</p>
            )}
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[10px] text-muted uppercase tracking-wider">Composite</p>
            <p className={`font-tabular text-3xl font-medium ${
              data.composite_score >= 70 ? 'text-velocity-high'
              : data.composite_score >= 40 ? 'text-velocity-medium'
              : 'text-velocity-low'
            }`}>
              {data.composite_score.toFixed(1)}
            </p>
          </div>
        </div>

        {/* Stat cells */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <StatCell label="Composite" value={data.composite_score.toFixed(1)} sub="0–100 signal" />
          <StatCell label="Source Diversity" value={String(data.source_diversity)} sub="sources breaching" />
          <StatCell label="Earliness" value={`${(data.earliness * 100).toFixed(0)}%`} sub="early vs mainstream" />
          <StatCell label="Status" value={data.breaching ? 'BREACH' : 'Monitor'} sub={data.status} />
        </div>

        {/* Velocity Trajectory Chart — the validation instrument */}
        <div className="card p-4 mb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-primary">Velocity Trajectory</h2>
            <span className="text-[10px] text-muted">composite score over time · daily</span>
          </div>
          {chartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm text-muted">
              No velocity history yet. Run ingestion to populate.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
                <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: CHART_COLORS.axis }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: CHART_COLORS.axis }}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 100]}
                />
                <Tooltip
                  contentStyle={{
                    background: '#161b22',
                    border: '1px solid #21262d',
                    borderRadius: 6,
                    fontSize: 11,
                    color: '#e6edf3',
                  }}
                  formatter={(v: number) => [v.toFixed(1), 'score']}
                />
                {/* Z=2 threshold line */}
                <ReferenceLine y={50} stroke="#f0a500" strokeDasharray="4 4" strokeWidth={1}
                  label={{ value: 'threshold', position: 'right', fontSize: 9, fill: '#f0a500' }} />
                <Line
                  type="monotone"
                  dataKey="composite_score"
                  stroke={CHART_COLORS.composite}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: CHART_COLORS.composite, stroke: '#0d1117', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Per-source breakdown */}
        <div className="card p-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Source Breakdown</h2>
          <div className="overflow-x-auto">
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
                {data.per_source.map(s => (
                  <SourceRow key={s.source} {...s} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 pt-3 border-t border-surface-border flex gap-4 text-[10px] text-muted">
            <span><span className="text-accent font-medium">Z ≥ 2.0</span> = velocity breach</span>
            <span><span className="text-accent font-medium">CUSUM ≥ 4.0</span> = structural break</span>
          </div>
        </div>

        {/* P2 placeholder */}
        <div className="card p-6 border-dashed opacity-50">
          <p className="text-xs text-muted text-center">
            Confidence radar + value-chain map — Phase 2 / 3
          </p>
        </div>
      </div>
    </div>
  )
}
