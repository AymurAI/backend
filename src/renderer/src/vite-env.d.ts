/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_MODE: 'electron' | 'web'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
