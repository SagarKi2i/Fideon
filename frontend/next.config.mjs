/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  webpack: (config) => {
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
