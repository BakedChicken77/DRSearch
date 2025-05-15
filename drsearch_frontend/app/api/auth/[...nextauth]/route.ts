// app\api\auth\[...nextauth]\route.ts

// This file acts as the entry point for the NextAuth API route in the App Router structure. 
// Its primary job is to set up the route handler for handling authentication-related requests.

// Purpose of route.ts:
// Registers the API Route: It creates an API route that can handle requests to /api/auth/[...nextauth]. 
// In the App Router, route.ts is used to define how specific routes behave.
// Handles Authentication: By using NextAuth(authOptions) in this file, it links your authentication logic to the /api/auth/ route.
// Supports HTTP Methods: The line export { handler as GET, handler as POST }; allows the route to handle both GET and POST requests. 
// This is essential because NextAuth needs to process requests such as login (POST) and fetching session data (GET).
// Without this file, the NextAuth routes like /api/auth/session or /api/auth/signin wouldn't work because there would be no route handler in place.



import NextAuth from "next-auth";
import { authOptions } from "../../../../lib/auth"; // path to `authOptions`

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
