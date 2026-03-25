import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  // Match Next/automatic JSX: components may omit `import React` (named hooks only).
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
