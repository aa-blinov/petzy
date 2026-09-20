import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(() => {
  // Use root path everywhere for simplicity
  const basePath = '/';
  
  return {
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon-192.svg', 'icon-512.svg', 'logo.svg'],
      manifest: {
        name: 'Petzy',
        short_name: 'Petzy',
        description: 'Pet health tracking application',
        theme_color: '#000000',
        background_color: '#000000',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: `${basePath}icon-192.svg`,
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          },
          {
            src: `${basePath}icon-512.svg`,
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
        // Vite emits <link rel="modulepreload" crossorigin> for every
        // vendor chunk. Workbox's navigation-fallback handler intercepts
        // those as navigations and throws "cross-origin service worker
        // resource mismatch" in the console — the preloads become
        // dead weight. Tell Workbox to keep its hands off hashed asset
        // bundles; the browser's HTTP cache + Workbox precache handle
        // them just fine.
        navigateFallbackDenylist: [/^\/assets\//],
        runtimeCaching: [
          {
            // No API response is ever served from a cache.
            //
            // This used to be NetworkFirst with a 60-second TTL (and
            // /api/pets was CacheFirst for five minutes). Both were a
            // bad trade for a health diary: a one-minute window buys
            // essentially no offline capability — anything longer than
            // a minute offline and the cache is stale anyway — while
            // it did leave one user's pet roster and medical records
            // in Cache Storage on a possibly shared device, ready to
            // be served to whoever signed in next, and let a slow
            // backend (mid-deploy) answer from a stale entry so the
            // UI rendered old data and then corrected itself.
            //
            // It matters most for /auth/session, the app's "am I
            // signed in?" probe: a cached 200 there would keep a
            // signed-out user looking signed in, and it has to fail
            // loudly during a deploy rather than answer from a stale
            // entry.
            //
            // The app shell is still precached, so the PWA installs
            // and launches offline; data simply requires the network
            // and says so when it is missing.
            urlPattern: /^\/api\/.*/i,
            handler: 'NetworkOnly',
          }
        ]
      }
    })
  ],
  // Use root path everywhere
  base: basePath,
  build: {
    // Enable chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Split vendor code
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-antd': ['antd-mobile', 'antd-mobile-icons'],
          'vendor-form': ['react-hook-form', '@hookform/resolvers', 'zod'],
          'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
        },
      },
    },
    // Increase chunk size warning limit
    chunkSizeWarningLimit: 600,
    // Minification
    minify: 'terser' as const,
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.log in production
        drop_debugger: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
        modifyVars: {},
      },
    },
  },
  server: {
    port: 5173, // Vite default port for local dev
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false
      }
    }
  },
  // `vite preview` serves the production build — the only local way to
  // exercise the service worker, which is disabled under `vite dev`.
  // It needs the same API proxy as the dev server or every request
  // 404s against the preview server itself.
  preview: {
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
  };
})
