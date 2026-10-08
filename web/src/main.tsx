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
