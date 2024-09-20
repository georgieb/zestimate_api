import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'development' ? '/' : '/repositories/zestimate_api/zestimate-frontend/zestimate-app/',
  build: {
    outDir: 'dist', // Ensure the output directory is set to 'dist'
  },
}))
