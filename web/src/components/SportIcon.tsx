import type { SportSummary } from '../lib/types'

function PickleballGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true">
      <rect x="4" y="2" width="12" height="14" rx="5" fill="currentColor" />
      <rect x="8.4" y="15" width="3.2" height="7" rx="1.4" fill="currentColor" />
      <circle cx="18.5" cy="17.5" r="3.5" fill="#e0fe2c" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  )
}

// Sports can use an emoji, or a `cm:` key for a glyph bundled with the app.
const GLYPHS: Record<string, () => React.JSX.Element> = { 'cm:pickleball': PickleballGlyph }

export function SportIcon({ sport, size = 'md' }: { sport: Pick<SportSummary, 'icon' | 'name'>; size?: 'sm' | 'md' | 'lg' }) {
  const Glyph = GLYPHS[sport.icon]
  return (
    <span className={`sport-icon sport-icon-${size}`} aria-hidden="true">
      {Glyph ? <Glyph /> : sport.icon || sport.name.slice(0, 1)}
    </span>
  )
}
