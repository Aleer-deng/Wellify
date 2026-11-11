import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
const backend = { target: process.env.WELLIFY_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: false };
const proxy = { '/api': backend, '/auth': backend };
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const allowed = new Set(['VITE_API_BASE_URL', 'VITE_HRW_ISSUER']);
  for (const key of Object.keys(env)) {
    if (!allowed.has(key)) throw new Error(`Refusing to expose unapproved browser environment variable: ${key}`);
  }
  if (mode === 'production' && env.VITE_API_BASE_URL && !env.VITE_API_BASE_URL.startsWith('/') && !env.VITE_API_BASE_URL.startsWith('https://')) {
    throw new Error('Production API URLs must use HTTPS or a same-origin path.');
  }
  const csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://horizon-testnet.stellar.org https://friendbot.stellar.org; object-src 'none'; base-uri 'none'; form-action 'self' https://accounts.google.com https://appleid.apple.com https://login.microsoftonline.com";
  return { plugins: [react(), {
    name: 'production-security-policy', apply: 'build',
    transformIndexHtml() { return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: csp }, injectTo: 'head-prepend' }]; },
  }],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy }, preview: { proxy },
  };
});
