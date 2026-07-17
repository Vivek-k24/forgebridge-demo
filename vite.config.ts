import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/forgebridge-demo/',
  plugins: [react()],
});
