import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import '@fontsource-variable/inter'
import '@fontsource-variable/manrope'
import '@fontsource-variable/newsreader'
import '@fontsource-variable/newsreader/wght-italic.css'
import './styles/index.css'

import { App } from './App'
import { routerBasename } from './config/env'
import { AuthProvider } from './hooks/useAuth'
import { ToastProvider } from './hooks/useToast'
import { SubmissionDraftProvider } from './hooks/useSubmissionDraft'
import { AppErrorBoundary } from './components/common/AppErrorBoundary'

const container = document.getElementById('root')
if (!container) throw new Error('Root element not found')

createRoot(container).render(
  <StrictMode>
    <AppErrorBoundary>
      <BrowserRouter basename={routerBasename}>
        <AuthProvider>
          <ToastProvider>
            <SubmissionDraftProvider>
              <App />
            </SubmissionDraftProvider>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </AppErrorBoundary>
  </StrictMode>,
)
