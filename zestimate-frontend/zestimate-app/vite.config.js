import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/repositories/zestimate_api/zestimate-frontend/zestimate-app/', // Reflects your app's subdirectory
})


  