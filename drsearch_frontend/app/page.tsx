// app\page.tsx

// This is the file where the actual page content (in this case, the ChatWindow) is rendered. 
// It is the entry point for the specific route (likely the homepage / in this case). 
// The page.tsx file defines what gets rendered on the page itself, and since it uses ChakraProvider and ChatWindow, 
// this is the primary entry point for rendering the core content.


"use client";

import { ChatWindow } from "../app/components/ChatWindow";
import { ToastContainer } from "react-toastify";
import { ChakraProvider, Button, Center, Spinner } from "@chakra-ui/react";
import { useSession, signIn } from "next-auth/react";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== 'False';

export default function Home() {
  // Always call useSession at the top level
  const { data: session, status } = useSession();

  if (AUTH_ENABLED) {
    if (status === "loading") {
      // Render a loading state while session is being fetched
      return (
        <ChakraProvider>
          <Center height="100vh">
            <Spinner size="xl" />
          </Center>
        </ChakraProvider>
      );
    }

    if (status !== "authenticated"){
      // User is not authenticated, show sign-in button
      return (
        <ChakraProvider>
          <Center height="100vh">
            <Button onClick={() => signIn()}>Sign in</Button>
          </Center>
        </ChakraProvider>
      );
    }
  }

  // Render the chat window regardless of authentication status when AUTH_ENABLED is False
  return (
    <ChakraProvider>
      <ToastContainer />
      <ChatWindow
        titleText="DRS ASSISTANT"
        placeholder="How do I send a ticket to IT"
      />
    </ChakraProvider>
  );
}
