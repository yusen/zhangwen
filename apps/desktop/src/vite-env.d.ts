/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ZHANGWEN_API_BASE_URL?: string;
  readonly VITE_ZHANGWEN_HOST?: "web" | "tauri";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
