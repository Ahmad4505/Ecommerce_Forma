import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({plugins:[react(),tailwindcss()],server:{fs:{deny:[
 '.env','.env.*','*.{crt,pem}','**/.git/**',
 '**/backend/**','**/.setup/**','**/.aws/**','**/.codex/**','**/.agents/**',
 '**/.npmrc','**/*.log','**/.functional-audit-results/**','**/test-results/**',
]}}});
