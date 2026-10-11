// Type shim for vite.config.ts.
//
// tsconfig.json includes vite.config.ts in the type check but limits global types to "vite/client",
// and @types/node is not installed, so `import ... from 'node:url'` fails with TS2307.
// vite.config.ts uses exactly two things from that module; declare them here.
//
// Remove this file when @types/node is added to devDependencies (the real types would clash with it).
declare module 'node:url' {
  export function fileURLToPath(url: string | URL): string
  export const URL: typeof globalThis.URL
}
