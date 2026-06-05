import { LineChart, Line, Tooltip, ResponsiveContainer, YAxis } from 'recharts'
import type { VelocityPoint } from '../api/client'

interface Props {
  data: VelocityPoint[]
  height?: number
  showTooltip?: boolean
}

export function VelocitySparkline({ data, height = 36, showTooltip = false }: Props) {
  if (!data || data.length === 0) {
    return <div className="h-9 flex items-center justify-center text-xs text-muted">no data</div>
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <YAxis domain={['auto', 'auto']} hide />
        {showTooltip && (
          <Tooltip
            contentStyle={{
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: 6,
              fontSize: 11,
              color: '#e6edf3',
              padding: '4px 8px',
            }}
            formatter={(v: number) => [v.toFixed(1), 'score']}
            labelFormatter={(ts: string) => new Date(ts).toLocaleDateString()}
          />
        )}
        <Line
          type="monotone"
          dataKey="composite_score"
          stroke="#00e5a0"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: '#00e5a0' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
