import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { api, type ApiError } from '../lib/api'
import type { AppConfig, Category, Sport } from '../lib/types'
import { useAsync } from '../lib/useAsync'

interface CatalogValue {
  sports: Sport[]
  categories: Category[]
  config: AppConfig | null
  loading: boolean
  error: ApiError | null
  reload: () => void
  sport: (id: string | null | undefined) => Sport | undefined
}

const CatalogContext = createContext<CatalogValue | null>(null)

/** The sport catalog drives which controls each screen shows, so it is loaded once for the whole app. */
export function CatalogProvider({ children }: { children: ReactNode }) {
  const state = useAsync(() => Promise.all([api.sports(), api.categories(), api.config()]), [])

  const value = useMemo<CatalogValue>(() => {
    const [sports, categories, config] = state.data ?? [[], [], null]
    const byId = new Map(sports.map((item) => [item.id, item]))
    return {
      sports,
      categories,
      config,
      loading: state.loading && !state.data,
      error: state.data ? null : state.error,
      reload: state.reload,
      sport: (id) => (id ? byId.get(id) : undefined),
    }
  }, [state.data, state.loading, state.error, state.reload])

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCatalog(): CatalogValue {
  const context = useContext(CatalogContext)
  if (!context) throw new Error('useCatalog must be used inside CatalogProvider')
  return context
}
