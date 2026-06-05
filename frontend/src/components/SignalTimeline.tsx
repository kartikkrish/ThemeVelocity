import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { api } from '../api/client'

const SOURCE_COLORS: Record<string, string> = {
  edgar:  '#00e5a0',
  hn:     '#60a5fa',
  gdelt:  '#f59e0b',
  reddit: '#f97316',
  rss:    '#a78bfa',
}

interface Props {
  themeId: string
}

export function SignalTimeline({ themeId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['signal-timeline', themeId],
    queryFn: () => api.getSignalTimeline(themeId),
    staleTime: 60_000,
  })

  if (isLoading) {
    return <div className="h-40 rounded bg-surface-border/20 animate-pulse" />
  }

  if (!data) return null

  const sources = Object.keys(data).filter(src => data[src].length > 0)
  if (sources.length === 0) {
    return (
      <div className="h-24 flex items-center justify-center text-sm text-muted">
        No per-source history yet — run ingestion first.
      </div>
    )
  }

  // Build a merged timeline keyed by ts
  const tsMap: Record<string, Record<string, number>> = {}
  for (const src of sources) {
    for (const pt of data[src]) {
      const label = new Date(pt.ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      if (!tsMap[label]) tsMap[label] = {}
      tsMap[label][src] = pt.zscore
    }
  }

  const chartData = Object.entries(tsMap)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, vals]) => ({ label, ...vals }))

  const GRID = '#21262d'
  const AXIS = '#8b949e'

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 10, fill: AXIS }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 10, fill: AXIS }} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: '#161b22', border: '1px solid #21262d', borderRadius: 6, fontSize: 11, color: '#e6edf3' }}
          formatter={(v: number, name: string) => [v.toFixed(2), name.toUpperCase()]}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 11, color: AXIS, paddingTop: 8 }}
          formatter={(v: string) => v.toUpperCase()}
        />
        <ReferenceLine y={2} stroke="#f0a500" strokeDasharray="4 4" strokeWidth={1}
          label={{ value: 'Z≥2', position: 'right', fontSize: 9, fill: '#f0a500' }} />
        {sources.map(src => (
          <Line
            key={src}
            type="monotone"
            dataKey={src}
            stroke={SOURCE_COLORS[src] ?? '#94a3b8'}
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
