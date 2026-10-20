import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // The app's own logic runs in a browser: localStorage, the caches API, timers.
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
  },
})
