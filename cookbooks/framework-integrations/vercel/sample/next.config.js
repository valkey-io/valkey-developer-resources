/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // @valkey/valkey-glide is a native Node.js addon with compiled binary files.
  // The Edge Runtime cannot execute them, so we exclude it from webpack bundling
  // and let Node.js load it from node_modules at runtime.
  serverExternalPackages: ['@valkey/valkey-glide'],
}

module.exports = nextConfig
