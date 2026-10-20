import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // The app's own logic runs in a browser: localStorage, the caches API, timers.
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    // Two workers, not one per core. Every worker is a separate process with its own
    // browser environment, and the machine may already be busy: the backend suite takes
    // every core, and the browser checks run next to it. The whole set takes seconds
    // this way, and nothing else is slowed down by it.
    maxWorkers: 2,
    coverage: {
      provider: 'v8',
      // The app's own logic, not the markup around it.
      include: ['src/utils/**', 'src/hooks/**'],
      reporter: ['text-summary', 'json-summary'],
    },
  },
})
