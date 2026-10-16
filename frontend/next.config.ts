import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a self-contained server with only the files it needs, so the
  // container does not carry node_modules. Still the documented approach
  // for Docker in Next 16.
  output: "standalone",
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
