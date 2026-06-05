const BASE = '/api'

export interface ThemeHeat {
  theme_id: string
  name: string
  composite_score: number
  source_diversity: number
  earliness: number
  breaching: boolean
  ts: string
}

export interface SourceSnapshot {
  source: string
  zscore: number
  cusum: number
  velocity: number
  acceleration: number
  count_1d: number
}

export interface VelocityPoint {
  ts: string
  composite_score: number
  source_diversity: number
  earliness: number
  breaching: boolean
}

export interface ThemeDetail {
  theme_id: string
  name: string
  primitive: string | null
  status: string
  composite_score: number
  source_diversity: number
  earliness: number
  breaching: boolean
  per_source: SourceSnapshot[]
  velocity_history: VelocityPoint[]
}

export interface AlertItem {
  alert_id: string
  theme_id: string
  fired_at: string
  composite_score: number
  acknowledged: boolean
}

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: 'POST' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  getHeat: (limit = 20) => get<ThemeHeat[]>('/themes/heat', { limit }),
  getTrending: (tab = 'daily', limit = 20) => get<ThemeHeat[]>('/themes/trending', { tab, limit }),
  getTheme: (id: string) => get<ThemeDetail>(`/themes/${id}`),
  getAlerts: (limit = 50) => get<AlertItem[]>('/alerts', { limit }),
  triggerIngest: () => post<{ status: string }>('/ingest/trigger'),
  runVelocity: () => post<{ computed: number; breaching: string[] }>('/velocity/run'),
}
