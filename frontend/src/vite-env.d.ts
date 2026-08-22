/// <reference types="vite/client" />

declare module '*.jsx' {
  const component: React.ComponentType<Record<string, unknown>>
  export default component
}

declare module 'three';
