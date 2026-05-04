const isWindows = process.platform === "win32";
// Docker/Linux/CI use standalone by default. On Windows, set NEXT_STANDALONE=1 for
// packaged Electron builds (standalone + outputFileTracing: false — see below).
const useStandalone =
  !isWindows || process.env.NEXT_STANDALONE === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(useStandalone ? { output: "standalone" } : {}),
  webpack: (config) => {
    // Treat the PDF.js worker as a file asset so it isn't parsed/minified as JS.
    config.module.rules.push({
      test: /pdf\\.worker\\.min\\.mjs$/,
      type: "asset/resource",
    });
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      "node:fs": false,
      "node:https": false,
      fs: false,
      https: false,
      path: false,
      os: false,
    };
    config.resolve.fallback = {
      ...(config.resolve.fallback || {}),
      fs: false,
      https: false,
      path: false,
      os: false,
    };
    return config;
  },
};

export default nextConfig;