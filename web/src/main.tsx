import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import './index.css'
import App from './App.tsx'
import { AuthProvider } from './state/auth'
import { CatalogProvider } from './state/catalog'
import { NotificationsProvider } from './state/notifications'
import { PlaceProvider } from './state/place'
import { ToastProvider } from './state/toast'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <CatalogProvider>
          <AuthProvider>
            <NotificationsProvider>
              <PlaceProvider>
                <App />
              </PlaceProvider>
            </NotificationsProvider>
          </AuthProvider>
        </CatalogProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)

// The service worker makes the app installable and lets its shell open offline.
// It is only registered for production builds so it never interferes with development.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}
