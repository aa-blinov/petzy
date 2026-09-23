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
