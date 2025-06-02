// This is the file where the actual page content (in this case, the ChatWindow) is rendered.
// It is the entry point for the specific route (likely the homepage / in this case).
// The page.tsx file defines what gets rendered on the page itself, and since it uses ChakraProvider and ChatWindow,
// this is the primary entry point for rendering the core content.

// app/page.tsx
'use client'

import { ChatWindow } from './components/ChatWindow'
import { ToastContainer } from 'react-toastify'
import { Button, Center, Spinner } from '@chakra-ui/react'
import { useSession, signIn } from 'next-auth/react'

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== 'False'

export default function Home() {
  const { data: session, status } = useSession()

  if (AUTH_ENABLED) {
    if (status === 'loading') {
      return (
        <Center height="100vh">
          <Spinner size="xl" />
        </Center>
      )
    }
    if (status !== 'authenticated') {
      return (
        <Center height="100vh">
          <Button onClick={() => signIn()}>Sign in</Button>
        </Center>
      )
    }
  }

  return (
    <>
      <ToastContainer />
      <ChatWindow
        titleText="DRS ASSISTANT"
        placeholder="How do I send a ticket to IT"
      />
    </>
  )
}
