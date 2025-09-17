import AzureADProvider, { AzureADProfile } from "next-auth/providers/azure-ad";
import CredentialsProvider from "next-auth/providers/credentials";
import { NextAuthOptions, User, Session, DefaultSession } from "next-auth";
import { JWT } from "next-auth/jwt";
import { TokenSetParameters } from "openid-client";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "False";
const API_SCOPE = process.env.NEXT_PUBLIC_AZURE_AD_API_SCOPE; // Replace with your actual API scope
const NEXT_AUTH_DEBUG_MODE = process.env.NEXT_AUTH_DEBUG_MODE === "true"; // Default debug mode to false if not set

console.log("Auth Enabled:", AUTH_ENABLED);

// Define a custom JWT interface to include our custom properties
interface CustomJWT extends JWT {
  accessToken?: string;
  accessTokenExpires?: number;
  refreshToken?: string;
  isAdmin?: boolean;
  error?: string;
}

// Function to configure identity providers like Azure AD
const configureIdentityProvider = () => {
  const providers = [];

  // Retrieve list of admin email addresses for access control, if specified
  const adminEmails = process.env.ADMIN_EMAIL_ADDRESS?.split(",").map((email) =>
    email.toLowerCase().trim(),
  );

  // Configure provider based on AUTH_ENABLED flag
  if (AUTH_ENABLED) {
    // Configure Azure AD Provider for production and secure environments
    if (
      process.env.NEXT_PUBLIC_AZURE_AD_CLIENT_ID &&
      process.env.AZURE_AD_CLIENT_SECRET &&
      process.env.NEXT_PUBLIC_AZURE_AD_TENANT_ID
    ) {
      providers.push(
        AzureADProvider({
          clientId: process.env.NEXT_PUBLIC_AZURE_AD_CLIENT_ID!,
          clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
          tenantId: process.env.NEXT_PUBLIC_AZURE_AD_TENANT_ID!,
          authorization: {
            params: {
              scope: `openid profile email offline_access ${API_SCOPE}`,
              redirect_uri: process.env.NEXT_PUBLIC_AZURE_AD_REDIRECT_URI!, // Example: Redirect to localhost:3000 in development
            },
          },
          async profile(
            profile: AzureADProfile,
            tokens: TokenSetParameters,
          ): Promise<User> {
            // Custom logic to ensure 'id' is set and handle admin check
            const isAdmin =
              adminEmails?.includes(profile.email?.toLowerCase() ?? "") ||
              adminEmails?.includes(
                profile.preferred_username?.toLowerCase() ?? "",
              ) ||
              false;

            const user: User = {
              id: profile.sub, // Ensure 'id' is set
              name: profile.name ?? profile.nickname ?? "Guest",
              email: profile.email ?? "",
              image: profile.picture ?? "",
              isAdmin, // Ensure isAdmin is always a boolean
            };

            return user;
          },
        }),
      );
    }
  } else {
    // Configure CredentialsProvider for development mode to bypass authentication
    providers.push(
      CredentialsProvider({
        name: "Development Login",
        credentials: {
          username: {
            label: "Username",
            type: "text",
            placeholder: "Enter any username",
          },
        },
        async authorize(credentials) {
          // Accept any username and assign a default user profile for development
          return {
            id: "dev-user",
            name: credentials?.username || "Dev User",
            isAdmin: true,
          } as User;
        },
      }),
    );
  }

  return providers;
};

// NextAuth configuration options
export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET, // Secret for signing JWT tokens
  providers: configureIdentityProvider(), // Setup providers based on environment (Azure AD for production)
  debug: NEXT_AUTH_DEBUG_MODE, // Enable debug mode for NextAuth.js
  callbacks: {
    // Callback to handle JWT token management
    async jwt({ token, account, user }): Promise<CustomJWT> {
      let customToken = token as CustomJWT;

      // Initial sign in
      if (account && user) {
        customToken = {
          accessToken: account.access_token,
          accessTokenExpires: account.expires_at
            ? account.expires_at * 1000
            : undefined, // Convert to milliseconds
          refreshToken: account.refresh_token,
          isAdmin: (user as User & { isAdmin: boolean }).isAdmin,
        };
        return customToken;
      }

      // Return previous token if the access token has not expired yet
      if (
        customToken.accessTokenExpires &&
        Date.now() < customToken.accessTokenExpires
      ) {
        return customToken;
      }

      // Access token has expired, try to refresh it
      if (customToken.refreshToken) {
        return await refreshAccessToken(customToken);
      } else {
        // No refresh token available, cannot refresh access token
        return { ...customToken, error: "RefreshTokenError" };
      }
    },
    // Callback to handle session creation and management
    async session({ session, token }) {
      const customToken = token as CustomJWT;

      // Pass the accessToken and isAdmin flag to the session
      session.accessToken = customToken.accessToken;
      session.error = customToken.error;
      if (session.user) {
        session.user.isAdmin = customToken.isAdmin ?? false;
      }
      return session;
    },
  },
  // Use JWT-based sessions
  session: {
    strategy: "jwt",
    maxAge: 60 * 60, // 1 hour
  },
};

// Function to refresh an expired access token
async function refreshAccessToken(token: CustomJWT): Promise<CustomJWT> {
  try {
    const url = `https://login.microsoftonline.us/${process.env.NEXT_PUBLIC_AZURE_AD_TENANT_ID}/oauth2/v2.0/token`;

    const params = new URLSearchParams();
    params.append("client_id", process.env.NEXT_PUBLIC_AZURE_AD_CLIENT_ID!);
    params.append("client_secret", process.env.AZURE_AD_CLIENT_SECRET!);
    params.append("grant_type", "refresh_token");
    params.append("refresh_token", token.refreshToken!);
    params.append("scope", `openid profile email offline_access ${API_SCOPE}`);

    const response = await fetch(url, {
      method: "POST",
      body: params,
    });
    const refreshedTokens = await response.json();

    if (!response.ok) {
      throw refreshedTokens;
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000, // Expires in milliseconds
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken, // Fall back to old refresh token if new one isn't returned
    };
  } catch (error) {
    console.error("Failed to refresh access token", error);
    return { ...token, error: "RefreshAccessTokenError" };
  }
}
