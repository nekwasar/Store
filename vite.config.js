import { defineConfig } from 'vite'
import legacy from '@vitejs/plugin-legacy'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  base: '/static/dist/',
  plugins: [
    legacy({
      targets: ['defaults', 'not IE 11'],
    }),
    visualizer({
      filename: 'docs/bundle-report.html',
      open: false,
      gzipSize: true,
    }),
  ],
  build: {
    manifest: true,
    outDir: 'static/dist',
    cssMinify: 'esbuild',
    minify: 'terser',
    target: 'es2015',
    assetsInlineLimit: 4096,
    chunkSizeWarningLimit: 250,
    rollupOptions: {
      input: {
        main: 'static_src/js/main.js',
        style: 'static_src/scss/style.scss',
      },
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/chart.js')) return 'vendor-chart';
          if (id.includes('node_modules/dropzone')) return 'vendor-dropzone';
          if (id.includes('node_modules/choices.js')) return 'vendor-choices';
          if (id.includes('node_modules/flatpickr')) return 'vendor-flatpickr';
          if (id.includes('node_modules/notyf')) return 'vendor-notyf';
          if (id.includes('node_modules/bootstrap')) return 'vendor-bootstrap';
          if (id.includes('node_modules/alpinejs')) return 'vendor-alpine';
          if (id.includes('node_modules')) return 'vendor-other';
        },
      },
    },
  },
})
