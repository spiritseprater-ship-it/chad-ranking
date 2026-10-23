import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { PreviewStrip } from '@/components/common/BackendBanner'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

function ScrollManager() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) {
      const target = document.getElementById(hash.replace('#', ''))
      if (target) {
        const top = target.getBoundingClientRect().top + window.scrollY - 84
        const prefersReducedMotion = window.matchMedia(
          '(prefers-reduced-motion: reduce)',
        ).matches
        window.scrollTo({ top, behavior: prefersReducedMotion ? 'auto' : 'smooth' })
        return
      }
    }
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [pathname, hash])

  return null
}

export function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-md focus:bg-forest focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>
      <PreviewStrip />
      <Navbar />
      <main id="main-content" className="flex-1">
        <Outlet />
      </main>
      <Footer />
      <ScrollManager />
    </div>
  )
}
