declare module 'react' {
  export function useState<S>(initialState?: S | (() => S)): [S, any];
  export function useEffect(effect: () => void | (() => void), deps?: readonly any[]): void;
  export const ReactNode: any;
}

declare module 'react/jsx-runtime' {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
}

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
  interface Element {}
}

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  [key: string]: any;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
