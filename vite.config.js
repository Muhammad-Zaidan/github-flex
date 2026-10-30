import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' keeps asset paths relative so the build works on GitHub Pages
// (https://<user>.github.io/github-flex/) as well as Vercel/Netlify roots.
export default defineConfig({
  plugins: [react()],
  base: './',
});
