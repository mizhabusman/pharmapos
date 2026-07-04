import process from 'node:process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    // Honour a PORT env var (used by preview tooling); default to 5173.
    port: Number(process.env.PORT) || 5173,
  },
})