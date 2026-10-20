import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target =
    env.VITE_API_PROXY_TARGET?.trim() ||
    "http://transcributed.homelab.home.arpa";

  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": { target, changeOrigin: true },
        "/healthz": { target, changeOrigin: true },
        "/readyz": { target, changeOrigin: true },
        "/docs": { target, changeOrigin: true },
        "/openapi.json": { target, changeOrigin: true },
      },
    },
  };
});
