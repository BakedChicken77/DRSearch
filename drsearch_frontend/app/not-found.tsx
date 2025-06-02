// app/not-found.tsx
'use client'

import { Providers } from '@/components/providers'
import Link from 'next/link'

export default function NotFound() {
  return (
    <Providers>
      <div className="flex flex-col items-center justify-center h-screen p-8">
        <h1 className="text-3xl mb-4">404 – Page Not Found</h1>
        <Link href="/" className="text-blue-600 underline">
          Go back home
        </Link>
      </div>
    </Providers>
  )
}
