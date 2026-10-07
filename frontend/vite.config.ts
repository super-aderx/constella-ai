import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The API (backend/), started with `fastapi dev`.
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
})
