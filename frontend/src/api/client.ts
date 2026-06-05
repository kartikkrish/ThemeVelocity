const BASE = '/api'

export interface ThemeHeat {
  theme_id: string
  name: string
  composite_score: number
  source_diversity: number
  earliness: number
  breaching: boolean
  ts: string
  // Phase 2 — nullable until synthesis runs
  one_line_thesis?: string | null
  catalyst_type?: string | null
  maturity_stage?: string | null
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

export interface SynthesisData {
  one_line_thesis: string
  catalyst_type: string
  catalyst_detail: string
  maturity_stage: string
  is_real_theme: boolean
  key_entities: string[]
  epistemic_tag: string
  noise_reason?: string | null
}

export interface ConfidenceData {
  c_velocity: number
  c_source: number
  c_catalyst: number
  c_earliness: number
  c_linkage: number
  c_liquidity: number
  c_total: number
  epistemic_tag: string
}

export interface BeneficiaryNode {
  node_role: string
  company_name: string
  ticker: string
  exchange: string
  linkage_tightness: string
  justification: string
  epistemic_tag: string
}

export interface IndiaCrossmapNode {
  node_role: string
  company_name: string
  ticker: string
  exchange: string
  linkage_tightness: string
  justification: string
  liquidity_flag: string
  epistemic_tag: string
}

export interface WatchlistItem {
  theme_id: string
  name: string
  pinned_at: string
  composite_score: number
  source_diversity: number
  earliness: number
  breaching: boolean
  ts: string
  one_line_thesis?: string | null
  maturity_stage?: string | null
}

export interface SignalTimelinePoint {
  ts: string
  zscore: number
  cusum: number
  velocity: number
  count: number
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
  // Phase 2+
  synthesis?: SynthesisData | null
  confidence?: ConfidenceData | null
  beneficiaries: BeneficiaryNode[]
  india_crossmap: IndiaCrossmapNode[]
  india_exposure_rating?: string | null
}

export interface AlertItem {
  alert_id: string
  theme_id: string
  theme_name: string
  fired_at: string
  composite_score: number
  one_line_thesis?: string | null
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

export interface ModelSettings {
  provider: 'anthropic' | 'gemini' | 'ollama'
  api_key_set: boolean
  api_key_masked: string | null
  base_url: string
  synthesis_model: string
  value_chain_model: string
}

export interface ModelSettingsUpdate {
  provider: string
  api_key?: string
  base_url?: string
  synthesis_model: string
  value_chain_model: string
}

export interface ModelTestResult {
  ok: boolean
  message: string
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  getHeat:             (limit = 20) => get<ThemeHeat[]>('/themes/heat', { limit }),
  getTrending:         (tab = 'daily', limit = 20) => get<ThemeHeat[]>('/themes/trending', { tab, limit }),
  getTheme:            (id: string) => get<ThemeDetail>(`/themes/${id}`),
  getAlerts:           (limit = 50) => get<AlertItem[]>('/alerts', { limit }),
  analyzeTheme:        (id: string) => post<{ status: string; theme_id: string }>(`/themes/${id}/analyze`),
  triggerIngest:       () => post<{ status: string }>('/ingest/trigger'),
  runVelocity:         () => post<{ computed: number; breaching: string[] }>('/velocity/run'),
  getModelSettings:    () => get<ModelSettings>('/settings/model'),
  saveModelSettings:   (body: ModelSettingsUpdate) => postJson<ModelSettings>('/settings/model', body),
  testModelSettings:   (body: ModelSettingsUpdate) => postJson<ModelTestResult>('/settings/model/test', body),
  getWatchlist:        () => get<WatchlistItem[]>('/watchlist'),
  toggleWatchlist:     (id: string) => post<{ theme_id: string; pinned: boolean }>(`/watchlist/${id}`),
  triggerIndia:        (id: string) => post<{ status: string; theme_id: string }>(`/themes/${id}/india`),
  getSignalTimeline:   (id: string) => get<Record<string, SignalTimelinePoint[]>>(`/themes/${id}/signal-timeline`),
}
