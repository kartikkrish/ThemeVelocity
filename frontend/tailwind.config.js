/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Design tokens — StockScans-adjacent dark fintech palette
        surface: {
          DEFAULT: '#0d1117',   // near-black base
          raised: '#161b22',    // card surface
          border: '#21262d',    // subtle divider
          hover: '#1c2128',
        },
        accent: {
          DEFAULT: '#00e5a0',   // sharp green — "accelerating"
          dim: '#00b37a',
          glow: 'rgba(0,229,160,0.15)',
        },
        muted: '#8b949e',
        text: {
          primary: '#e6edf3',
          secondary: '#8b949e',
        },
        velocity: {
          high: '#00e5a0',
          medium: '#f0a500',
          low: '#8b949e',
          breach: '#ff4d4d',
        },
        tag: {
          V: '#2d8cf0',
          E: '#f0a500',
          I: '#9b59b6',
        },
      },
      fontFamily: {
        display: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        tabular: ['"IBM Plex Mono"', 'monospace'],
      },
      animation: {
        'pulse-accent': 'pulse-accent 2s ease-in-out infinite',
        'draw-in': 'draw-in 0.6s ease-out forwards',
        'fade-up': 'fade-up 0.4s ease-out forwards',
      },
      keyframes: {
        'pulse-accent': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(0,229,160,0)' },
          '50%': { boxShadow: '0 0 0 6px rgba(0,229,160,0.15)' },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
