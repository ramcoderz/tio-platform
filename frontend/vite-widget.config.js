import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/widget-main.jsx'),
      name: 'TIOWidget',
      fileName: (format) => `tio-widget.${format}.js`,
      formats: ['umd', 'es'],
    },
    rollupOptions: {
      // We don't externalize react/react-dom because this is a standalone embed
      // that should work on sites that DON'T have React.
      output: {
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
        },
      },
    },
    outDir: 'dist-widget',
    emptyOutDir: true,
    cssCodeSplit: false, // Bundle all CSS into the JS or a single CSS file
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
});
