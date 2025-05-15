// lib\next-auth.d.ts


import NextAuth from "next-auth";

declare module "next-auth" {
  interface User {
    isAdmin: boolean; // Add isAdmin property to the User type
  }

  interface Session {
    accessToken?: string; // Add accessToken property to the Session
    user: User; // Include the modified User type with isAdmin in Session
    error?: string; // Add this line to include the `error` property
  }
}