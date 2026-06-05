import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ModelSettingsUpdate } from '../api/client'

// ── Provider definitions ────────────────────────────────────────────────────

const PROVIDERS = [
  {
    id: 'anthropic',
    name: 'Anthropic',
    tagline: 'Claude models — best tool-use reliability',
    icon: '◆',
    iconColor: 'text-violet-400',
    docsUrl: 'https://console.anthropic.com/',
    docsLabel: 'Get key at console.anthropic.com',
    defaultSynthesis: 'claude-haiku-4-5-20251001',
    defaultValueChain: 'claude-sonnet-4-6',
    needsKey: true,
    needsUrl: false,
    keyPlaceholder: 'sk-ant-…',
    urlPlaceholder: '',
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    tagline: 'Gemini models via Google AI Studio',
    icon: '✦',
    iconColor: 'text-sky-400',
    docsUrl: 'https://aistudio.google.com/',
    docsLabel: 'Get key at aistudio.google.com',
    defaultSynthesis: 'gemini-1.5-flash',
    defaultValueChain: 'gemini-1.5-pro',
    needsKey: true,
    needsUrl: false,
    keyPlaceholder: 'AIza…',
    urlPlaceholder: '',
  },
  {
    id: 'ollama',
    name: 'Ollama',
    tagline: 'Self-hosted — any Ollama model, no API key',
    icon: '⬡',
    iconColor: 'text-emerald-400',
    docsUrl: 'https://ollama.com/library',
    docsLabel: 'Browse models at ollama.com/library',
    defaultSynthesis: 'llama3.1',
    defaultValueChain: 'llama3.1:70b',
    needsKey: false,
    needsUrl: true,
    keyPlaceholder: '',
    urlPlaceholder: 'http://localhost:11434/v1',
  },
] as const

type ProviderId = typeof PROVIDERS[number]['id']

// ── Small helpers ────────────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] font-medium text-muted uppercase tracking-wider mb-1.5">{children}</p>
}

function FieldInput({
  value, onChange, placeholder, type = 'text', monospace = false,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
  monospace?: boolean
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-text-primary
        placeholder:text-muted focus:outline-none focus:border-accent/60 transition-colors
        ${monospace ? 'font-mono' : ''}`}
    />
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export function Settings() {
  const qc = useQueryClient()

  const { data: saved, isLoading } = useQuery({
    queryKey: ['model-settings'],
    queryFn: api.getModelSettings,
  })

  // Local form state
  const [provider, setProvider] = useState<ProviderId>('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [baseUrl, setBaseUrl] = useState('')
  const [synthesisModel, setSynthesisModel] = useState('')
  const [valueChainModel, setValueChainModel] = useState('')

  // Populate form once server data arrives
  useEffect(() => {
    if (!saved) return
    setProvider(saved.provider as ProviderId)
    setBaseUrl(saved.base_url || '')
    setSynthesisModel(saved.synthesis_model)
    setValueChainModel(saved.value_chain_model)
  }, [saved])

  const pDef = PROVIDERS.find(p => p.id === provider)!

  // When provider changes, reset models to defaults (unless user has typed something)
  const handleProviderSwitch = (id: ProviderId) => {
    const def = PROVIDERS.find(p => p.id === id)!
    setProvider(id)
    setSynthesisModel(def.defaultSynthesis)
    setValueChainModel(def.defaultValueChain)
    setBaseUrl(def.urlPlaceholder)
    setApiKey('')
  }

  const buildPayload = (keyOverride?: string): ModelSettingsUpdate => ({
    provider,
    api_key: keyOverride !== undefined ? keyOverride : (apiKey || undefined),
    base_url: baseUrl,
    synthesis_model: synthesisModel || pDef.defaultSynthesis,
    value_chain_model: valueChainModel || pDef.defaultValueChain,
  })

  // Save
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveMutation = useMutation({
    mutationFn: () => api.saveModelSettings(buildPayload()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['model-settings'] })
      setApiKey('')   // clear — key is now stored server-side
      setSaveState('saved')
      setTimeout(() => setSaveState('idle'), 3000)
    },
    onError: () => {
      setSaveState('error')
      setTimeout(() => setSaveState('idle'), 4000)
    },
  })

  // Test
  const [testState, setTestState] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [testMsg, setTestMsg] = useState('')
  const testMutation = useMutation({
    mutationFn: () => api.testModelSettings(buildPayload()),
    onSuccess: (res) => {
      setTestState(res.ok ? 'ok' : 'fail')
      setTestMsg(res.message)
      setTimeout(() => setTestState('idle'), 5000)
    },
    onError: (err) => {
      setTestState('fail')
      setTestMsg(String(err))
      setTimeout(() => setTestState('idle'), 5000)
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface px-4 py-8 max-w-2xl mx-auto space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 rounded-xl bg-surface-border/30 animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface px-4 py-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-base font-semibold text-text-primary">Model Settings</h1>
        <p className="text-xs text-muted mt-1">
          Choose which AI provider powers synthesis and value-chain analysis.
          Settings are saved to the database and take effect immediately — no restart needed.
        </p>
      </div>

      {/* ── Provider selector ── */}
      <div className="card p-4 mb-4">
        <Label>Provider</Label>
        <div className="grid grid-cols-3 gap-2">
          {PROVIDERS.map(p => (
            <button
              key={p.id}
              onClick={() => handleProviderSwitch(p.id)}
              className={`flex flex-col items-start gap-1.5 p-3 rounded-lg border transition-all text-left
                ${provider === p.id
                  ? 'border-accent/50 bg-accent/5'
                  : 'border-surface-border hover:border-surface-border/80 hover:bg-surface-hover'}`}
            >
              <span className={`text-lg leading-none ${p.iconColor}`}>{p.icon}</span>
              <span className="text-xs font-semibold text-text-primary">{p.name}</span>
              <span className="text-[10px] text-muted leading-snug">{p.tagline}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Credentials ── */}
      <div className="card p-4 mb-4 space-y-4">
        <Label>Credentials</Label>

        {pDef.needsKey && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[11px] text-muted">API Key</p>
              {saved?.api_key_set && !apiKey && (
                <span className="text-[10px] text-accent">
                  Key saved: {saved.api_key_masked}
                </span>
              )}
            </div>
            <div className="relative">
              <FieldInput
                value={apiKey}
                onChange={setApiKey}
                placeholder={saved?.api_key_set ? '(key saved — enter new one to replace)' : pDef.keyPlaceholder}
                type={showKey ? 'text' : 'password'}
                monospace
              />
              <button
                onClick={() => setShowKey(v => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted hover:text-text-secondary px-1"
              >
                {showKey ? 'hide' : 'show'}
              </button>
            </div>
            <p className="text-[10px] text-muted mt-1">{pDef.docsLabel}</p>
          </div>
        )}

        {pDef.needsUrl && (
          <div>
            <p className="text-[11px] text-muted mb-1.5">Endpoint URL</p>
            <FieldInput
              value={baseUrl}
              onChange={setBaseUrl}
              placeholder={pDef.urlPlaceholder}
              monospace
            />
            <p className="text-[10px] text-muted mt-1">
              Default: http://localhost:11434/v1 — change for remote Ollama or vLLM
            </p>
          </div>
        )}
      </div>

      {/* ── Models ── */}
      <div className="card p-4 mb-6 space-y-4">
        <div className="flex items-center justify-between">
          <Label>Models</Label>
          <button
            onClick={() => {
              setSynthesisModel(pDef.defaultSynthesis)
              setValueChainModel(pDef.defaultValueChain)
            }}
            className="text-[10px] text-muted hover:text-text-secondary transition-colors"
          >
            Reset to defaults
          </button>
        </div>

        <div>
          <p className="text-[11px] text-muted mb-1.5">
            Synthesis model
            <span className="ml-1 text-[10px] opacity-60">— one-line thesis, catalyst, maturity (faster/cheaper)</span>
          </p>
          <FieldInput
            value={synthesisModel}
            onChange={setSynthesisModel}
            placeholder={pDef.defaultSynthesis}
            monospace
          />
        </div>

        <div>
          <p className="text-[11px] text-muted mb-1.5">
            Value-chain model
            <span className="ml-1 text-[10px] opacity-60">— beneficiary mapping (more capable)</span>
          </p>
          <FieldInput
            value={valueChainModel}
            onChange={setValueChainModel}
            placeholder={pDef.defaultValueChain}
            monospace
          />
        </div>
      </div>

      {/* ── Actions ── */}
      <div className="flex items-center gap-3">
        {/* Save */}
        <button
          onClick={() => { setSaveState('saving'); saveMutation.mutate() }}
          disabled={saveMutation.isPending}
          className="px-4 py-2 rounded-md bg-accent text-surface text-sm font-semibold
            hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved ✓' : 'Save settings'}
        </button>

        {/* Test */}
        <button
          onClick={() => { setTestState('testing'); testMutation.mutate() }}
          disabled={testMutation.isPending}
          className="px-4 py-2 rounded-md border border-surface-border text-sm text-text-secondary
            hover:border-accent/40 hover:text-text-primary transition-colors disabled:opacity-50"
        >
          {testState === 'testing' ? 'Testing…' : 'Test connection'}
        </button>

        {/* Status feedback */}
        {saveState === 'error' && (
          <span className="text-xs text-red-400">Save failed</span>
        )}
        {testState === 'ok' && (
          <span className="text-xs text-accent">{testMsg}</span>
        )}
        {testState === 'fail' && (
          <span className="text-xs text-red-400">{testMsg}</span>
        )}
      </div>

      {/* ── Info footer ── */}
      <div className="mt-8 pt-4 border-t border-surface-border space-y-1">
        <p className="text-[11px] text-muted">
          <span className="text-text-secondary font-medium">What these models do:</span>{' '}
          When a theme crosses the alert threshold, the synthesis model writes a plain-English thesis
          and classifies the catalyst. The value-chain model then maps which companies benefit and how.
        </p>
        <p className="text-[11px] text-muted">
          <span className="text-text-secondary font-medium">Security note:</span>{' '}
          API keys are stored in the local SQLite database. Do not use this on a publicly-accessible server without additional access controls.
        </p>
      </div>
    </div>
  )
}
