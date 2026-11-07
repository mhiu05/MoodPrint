import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  envDir: "..",
  envPrefix: "VITE_PUBLIC_",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (/[\\/](@gsap|gsap)[\\/]/.test(id)) return "motion";
            if (
              /[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(
                id,
              )
            )
              return "react-vendor";
          }
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
