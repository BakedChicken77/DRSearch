/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_BUILD_SHA:
      process.env.NEXT_PUBLIC_BUILD_SHA ?? process.env.APP_BUILD_SHA ?? "",
    NEXT_PUBLIC_BUILD_SHA_SHORT:
      process.env.NEXT_PUBLIC_BUILD_SHA_SHORT ??
      process.env.APP_BUILD_SHA_SHORT ??
      "",
    NEXT_PUBLIC_BUILD_DATE:
      process.env.NEXT_PUBLIC_BUILD_DATE ?? process.env.APP_BUILD_DATE ?? "",
  },
  // output: 'standalone',
};

module.exports = nextConfig;
