import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
})
export default {
  base: '/zestimate-app/',  // or '/' if deployed to root
  // ... other config
}