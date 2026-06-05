import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { HeatTile } from '../components/HeatTile'
import { ThemeCard } from '../components/ThemeCard'

const TABS = ['Daily', 'Weekly'] as const
type Tab = typeof TABS[number]

function EmptyState({ msg }: { msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted gap-2">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.5l4-4 4 3 4-6 4 2" />
        <rect x="2" y="2" width="20" height="20" rx="3" strokeWidth="1" opacity="0.3" />
      </svg>
      <p className="text-sm">{msg}</p>
    </div>
  )
}

function ErrorState({ msg }: { msg: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-red-400 px-4 py-3 bg-red-900/10 rounded-lg border border-red-900/30">
      <span>⚠</span><span>{msg}</span>
    </div>
  )
}

export function Dashboard() {
  const [tab, setTab] = useState<Tab>('Daily')

  const heatQ = useQuery({
    queryKey: ['heat'],
    queryFn: () => api.getHeat(20),
  })

  const trendQ = useQuery({
    queryKey: ['trending', tab],
    queryFn: () => api.getTrending(tab.toLowerCase(), 20),
  })

  const heatData = heatQ.data ?? []
  const trendData = trendQ.data ?? []
  const breachingCount = trendData.filter(t => t.breaching).length

  return (
    <div className="min-h-screen bg-surface">
      {/* Theme Heat Strip */}
      <div className="border-b border-surface-border bg-surface-raised/50">
        <div className="px-4 py-2">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] font-medium text-muted uppercase tracking-widest">
              Theme Heat
            </span>
            {breachingCount > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">
                {breachingCount} breaching
              </span>
            )}
          </div>
          {heatQ.isError ? (
            <ErrorState msg="Could not load themes — is the backend running?" />
          ) : heatData.length === 0 ? (
            <p className="text-xs text-muted py-2">
              No data yet — trigger ingestion or wait for scheduler.
            </p>
          ) : (
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              {heatData.map((t, i) => (
                <HeatTile key={t.theme_id} theme={t} rank={i} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main content grid */}
      <div className="px-4 py-4 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Trending Themes panel — 2 cols */}
          <div className="lg:col-span-2">
            <div className="card">
              {/* Panel header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border">
                <h2 className="text-sm font-semibold text-text-primary">Trending Themes by Velocity</h2>
                <div className="flex gap-1">
                  {TABS.map(t => (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      className={`text-xs px-2.5 py-1 rounded transition-colors ${
                        tab === t
                          ? 'bg-accent/15 text-accent font-medium'
                          : 'text-muted hover:text-text-primary'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Theme cards */}
              <div className="p-4">
                {trendQ.isError ? (
                  <ErrorState msg="Could not load trending themes." />
                ) : trendQ.isLoading ? (
                  <div className="grid grid-cols-1 gap-3">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="h-28 rounded-lg bg-surface-border/30 animate-pulse" />
                    ))}
                  </div>
                ) : trendData.length === 0 ? (
                  <EmptyState msg="No themes yet. Trigger ingestion to populate." />
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {trendData.map((t, i) => (
                      <ThemeCard key={t.theme_id} theme={t} rank={i} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right panel: Quick actions + status */}
          <div className="flex flex-col gap-4">
            {/* System Status */}
            <div className="card p-4">
              <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
                System Status
              </h3>
              <div className="space-y-2">
                {[
                  { label: 'EDGAR', src: 'edgar', weight: '1.0' },
                  { label: 'Hacker News', src: 'hn', weight: '0.7' },
                  { label: 'GDELT', src: 'gdelt', weight: '0.6' },
                ].map(s => (
                  <div key={s.src} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                      <span className="text-xs text-text-secondary">{s.label}</span>
                    </div>
                    <span className="text-xs font-tabular text-muted">w={s.weight}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Manual controls */}
            <div className="card p-4">
              <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
                Controls
              </h3>
              <div className="space-y-2">
                <TriggerButton
                  label="Trigger Ingestion"
                  action={() => api.triggerIngest()}
                  desc="Fetch EDGAR + HN + GDELT now"
                />
                <TriggerButton
                  label="Recompute Velocity"
                  action={() => api.runVelocity()}
                  desc="Rerun Z-score + CUSUM for all themes"
                />
              </div>
            </div>

            {/* Legend */}
            <div className="card p-4">
              <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
                Score Guide
              </h3>
              <div className="space-y-1.5 text-xs">
                {[
                  { label: '70–100', desc: 'High velocity', cls: 'text-velocity-high' },
                  { label: '40–70', desc: 'Moderate signal', cls: 'text-velocity-medium' },
                  { label: '0–40', desc: 'Baseline / noise', cls: 'text-velocity-low' },
                ].map(g => (
                  <div key={g.label} className="flex items-center justify-between">
                    <span className={`font-tabular font-medium ${g.cls}`}>{g.label}</span>
                    <span className="text-muted">{g.desc}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-surface-border text-xs text-muted space-y-1">
                <p><span className="text-accent font-medium">BREACH</span> = Z≥2 or CUSUM≥4 across ≥2 sources</p>
                <p>Score = weighted Z × source-diversity bonus</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
function TriggerButton({
  label,
  action,
  desc,
}: {
  label: string
  action: () => Promise<unknown>
  desc: string
}) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')

  const run = async () => {
    setState('loading')
    try {
      await action()
      setState('done')
      setTimeout(() => setState('idle'), 3000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 3000)
    }
  }

  return (
    <button
      onClick={run}
      disabled={state === 'loading'}
      className="w-full text-left px-3 py-2 rounded-md border border-surface-border hover:border-accent/40 hover:bg-surface-hover transition-all disabled:opacity-50"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-primary">{label}</span>
        {state === 'loading' && <span className="text-[10px] text-muted animate-pulse">running…</span>}
        {state === 'done' && <span className="text-[10px] text-accent">done</span>}
        {state === 'error' && <span className="text-[10px] text-red-400">error</span>}
      </div>
      <p className="text-[10px] text-muted mt-0.5">{desc}</p>
    </button>
  )
}
