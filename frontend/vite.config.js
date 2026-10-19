import {defineConfig} from 'vite';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
export default defineConfig({root:path.resolve('frontend'),plugins:[tailwindcss()],build:{outDir:'../dist',emptyOutDir:true},server:{host:'127.0.0.1',port:5173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000'}}});
