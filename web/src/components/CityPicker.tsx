import { useState } from 'react'
import { api } from '../lib/api'
import type { Place } from '../lib/types'
import { useAsync } from '../lib/useAsync'

/** Find a city or municipality by typing part of its name. */
export function CityPicker({ value, onChange, label = 'City or municipality' }: { value: Place | null; onChange: (city: Place | null) => void; label?: string }) {
  const [query, setQuery] = useState('')
  const term = query.trim()
  const matches = useAsync(() => api.cities({ q: term }), [term], term.length >= 2)

  return (
    <div className="field">
      <span>{label}</span>
      {value ? (
        <div className="chip-row">
          <span className="chip chip-static">{value.name}</span>
          <button type="button" className="text-button" onClick={() => onChange(null)}>
            Change
          </button>
        </div>
      ) : (
        <>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Type at least two letters" aria-label={label} />
          <div className="chip-row">
            {term.length >= 2 &&
              matches.data?.slice(0, 8).map((item) => (
                <button type="button" key={item.code} className="chip" onClick={() => onChange({ code: item.code, name: item.name })}>
                  {item.name}
                </button>
              ))}
            {term.length >= 2 && matches.data?.length === 0 && <small>No city or municipality matches “{term}”.</small>}
          </div>
        </>
      )}
    </div>
  )
}
