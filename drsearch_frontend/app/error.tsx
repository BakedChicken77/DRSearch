// app/error.tsx
'use client'


import { Providers } from '@/components/providers'

interface ErrorProps { error: Error; reset: () => void }

export default function ErrorPage({ error, reset }: ErrorProps) {
  return (
    <Providers>
      <div className="flex flex-col items-center justify-center h-screen p-8">
        <h1 className="text-2xl mb-4">Something went wrong</h1>
        <pre className="mb-4 text-sm text-red-600">{error.message}</pre>
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded"
          onClick={() => reset()}
        >
          Try again
        </button>
      </div>
    </Providers>
  )
}
