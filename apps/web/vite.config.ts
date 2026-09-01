/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Os fluxos de interface compartilham mocks de browser e simulações de
    // relógio; executar arquivos em paralelo torna o timeout dependente da
    // carga da máquina em vez do comportamento que cada teste cobre.
    fileParallelism: false,
  },
})
