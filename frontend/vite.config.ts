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
      // generateSW (the default) has Workbox author the whole service
      // worker for us — no room to add our own `push`/`notificationclick`
      // listeners. injectManifest instead builds frontend/src/sw.ts,
      // which owns those listeners itself and calls precacheAndRoute()
      // with the same asset list generateSW would have produced.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
      },
      includeAssets: ['favicon.svg', 'icon.svg', 'apple-touch-icon.png', 'badge-96.png'],
      // The one manifest (a second, hand-written public/manifest.json with
      // a blue theme and SVG-only icons used to be linked first and win).
      // PNG icons: iOS ignores SVG for the home screen and several Android
      // launchers do too. The icon is a full-bleed square with the letter
      // inside the maskable safe zone, so it serves both purposes.
      manifest: {
        name: 'Petzy',
        short_name: 'Petzy',
        description: 'Кормление, вес, лекарства и документы питомца в одном месте',
        lang: 'ru',
        theme_color: '#FEFCF6',
        background_color: '#FAF6EF',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: `${basePath}icon-192.png`,
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable'
          },
          {
            src: `${basePath}icon-512.png`,
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          },
          {
            src: `${basePath}icon.svg`,
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any'
          }
        ]
      }
      // The `workbox: { navigateFallbackDenylist, runtimeCaching }` that
      // used to live here only applies to the generateSW strategy —
      // injectManifest ignores it silently. That same navigation-route
      // and NetworkOnly-for-/api/ behavior now lives directly in
      // frontend/src/sw.ts, with the same reasoning preserved there.
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
