import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` proxies the API to the FastAPI server on :8001.
// Prod: `npm run build` -> dist/, served by FastAPI.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: "http://localhost:8001", changeOrigin: true } } },
});
