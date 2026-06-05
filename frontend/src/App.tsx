import { Component, type ReactNode } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Nav } from './components/Nav'
import { Dashboard } from './pages/Dashboard'
import { ThemeDetail } from './pages/ThemeDetail'
import { Alerts } from './pages/Alerts'

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-surface flex items-center justify-center p-8">
          <div className="max-w-lg w-full card p-6 space-y-3">
            <p className="text-sm font-semibold text-red-400">Something went wrong</p>
            <pre className="text-[11px] text-muted bg-surface rounded p-3 overflow-auto whitespace-pre-wrap">
              {(this.state.error as Error).message}
            </pre>
            <button
              onClick={() => this.setState({ error: null })}
              className="text-xs text-accent hover:underline"
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <p className="text-muted text-sm">{title} — coming in later phases</p>
    </div>
  )
}

export default function App() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <main className="flex-1">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/theme/:id" element={<ThemeDetail />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/watchlist" element={<PlaceholderPage title="Watchlist" />} />
            <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
            <Route path="*" element={<PlaceholderPage title="404" />} />
          </Routes>
        </ErrorBoundary>
      </main>
      <footer className="border-t border-surface-border px-4 py-3 flex items-center justify-between">
        <span className="text-xs text-muted font-display">
          ThemeVelocity · Phase 1 Radar
        </span>
        <span className="text-xs text-muted">
          EDGAR · HN · GDELT
        </span>
      </footer>
    </div>
  )
}
