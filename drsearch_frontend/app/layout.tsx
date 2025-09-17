// This file defines the global layout structure for the app. It wraps every page and provides the overall HTML,
// body structure, and common layout components (such as a navigation bar, footer, or background styling).
// It is not responsible for rendering specific page content but ensures that all child pages follow a consistent layout.

// app/layout.tsx
import './globals.css'
import { Providers } from '@/components/providers'
import { BuildInfoWidget } from './components/BuildInfoWidget'

export const metadata = {
  title: 'DRSearch',
  description: 'DRSearch Assistant',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="h-full">
      <body
        className="inter h-full"
        style={{ background: 'rgb(212, 211, 203)' }}
      >
        <div className="flex flex-col h-full md:p-8">
          <Providers>
            {children}
            <BuildInfoWidget />
          </Providers>
        </div>
      </body>
    </html>
  )
}
