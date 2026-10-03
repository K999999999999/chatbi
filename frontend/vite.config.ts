import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.CHATBI_DEV_API_TARGET ?? 'http://127.0.0.1:8000';
export default defineConfig({
  plugins: [react()],
  cacheDir: process.env.CHATBI_DEV_API_TARGET ? '/tmp/chatbi-vite' : 'node_modules/.vite',
  server: { port: 5173, strictPort: true, proxy: {
    '/auth': apiTarget, '/api': apiTarget, '/health': apiTarget,
  } },
});
