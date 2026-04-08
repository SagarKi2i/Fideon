const isWindows = process.platform === "win32";
// Standalone needs outputFileTracing; on Windows tracing often hits EPERM on `trace`.
// Docker/Linux/CI use standalone. Set NEXT_STANDALONE=1 on Windows only if your
// environment can write trace files (needed for packaged Electron builds).
const useStandalone =
  !isWindows || process.env.NEXT_STANDALONE === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(useStandalone ? { output: "standalone" } : {}),
  ...(isWindows && !useStandalone ? { outputFileTracing: false } : {}),
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