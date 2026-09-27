import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // MapLibre starts its tile worker as an ES module worker, so bundle workers as ES modules too.
  worker: { format: 'es' },
})
