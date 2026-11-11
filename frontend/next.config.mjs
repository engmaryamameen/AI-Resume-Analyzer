const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // The browser only ever talks to this origin, so session cookies stay first-party.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
