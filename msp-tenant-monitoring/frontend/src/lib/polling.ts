/**
 * polling.ts — thin re-export shim.
 *
 * The real implementations live in autoRefresh.tsx (context-based).
 * This file exists only so that any import of `@/lib/polling` continues
 * to compile without changes; the actual hooks come from autoRefresh.tsx.
 */
export { useAutoRefresh, useAutoEnabled } from './autoRefresh'
