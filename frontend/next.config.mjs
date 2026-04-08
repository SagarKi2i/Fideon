/** @type {import('next').NextConfig} */
const nextConfig = {
  // Work around occasional Windows permission locks on `.next/trace`
  // by using a separate build output directory.
  distDir: ".next-build",
  // Also disable output file tracing (writes `.next*/trace`) which can fail on some Windows setups.
  outputFileTracing: false,
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