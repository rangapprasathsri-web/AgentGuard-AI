/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--color-ink)',
        muted: 'var(--color-muted)',
        hair: 'var(--color-hair)',
        line: 'var(--color-line)',
        surface: 'var(--color-surface)',
        card: 'var(--color-card)',
        page: 'var(--color-page)',
        brand: {
          DEFAULT: 'var(--color-brand)',
          hover: 'var(--color-brand-hover)',
          ink: 'var(--color-brand-ink)',
          soft: 'var(--color-brand-soft)',
        },
        learn: {
          DEFAULT: 'var(--color-learn)',
          ink: 'var(--color-learn-ink)',
          soft: 'var(--color-learn-soft)',
        },
        ok: {
          DEFAULT: 'var(--color-ok)',
          soft: 'var(--color-ok-soft)',
          dot: 'var(--color-ok-dot)',
        },
        warn: {
          DEFAULT: 'var(--color-warn)',
          soft: 'var(--color-warn-soft)',
          dot: 'var(--color-warn-dot)',
        },
        bad: {
          DEFAULT: 'var(--color-bad)',
          soft: 'var(--color-bad-soft)',
          dot: 'var(--color-bad-dot)',
        },
        metric: 'var(--color-metric)',
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          '"Liberation Mono"',
          '"Courier New"',
          'monospace',
        ],
      },
      letterSpacing: {
        tightest: '-0.05em',
        tighter: '-0.04em',
        tight: '-0.02em',
      },
      borderRadius: {
        'panel': '48px',
        'panel-sm': '40px',
        'inner': '22px',
      },
      boxShadow: {
        'soft': '0 8px 30px rgba(0, 0, 0, 0.05)',
        'soft-lg': '0 20px 60px rgba(0, 0, 0, 0.08)',
        'panel': '0 24px 80px rgba(0, 0, 0, 0.12)',
      },
    },
  },
  plugins: [],
};
