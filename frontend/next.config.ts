import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone is for the Docker image: it emits a self-contained server
  // so the container carries no node_modules. Vercel builds its own
  // serverless output and standalone interferes with that -- the symptom
  // is the deployment returning 404 NOT_FOUND from the edge with no page
  // served at all. VERCEL is set in their build environment, so the
  // Docker path keeps standalone and Vercel gets the default.
  ...(process.env.VERCEL ? {} : { output: "standalone" as const }),
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
