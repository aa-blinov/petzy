import { defineConfig } from 'vitest/config'

// https://vitest.dev/config/
export default defineConfig({
  test: {
    // The app's own logic runs in a browser: localStorage, the caches API, timers.
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts'],
  },
})
