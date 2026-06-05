/**
 * Centralised localStorage key constants and shared interval values.
 * Import from here instead of re-defining in individual modules.
 */

export const STORAGE_KEYS = {
  auto: 'msp.auto',
  drilldownTypes: 'msp.drilldown.types',
  theme: 'msp.theme',
  exchangeShowSteps: 'msp.exchange.showSteps',
  creds: 'msp.creds',
  baseUrl: 'msp.base_url',
} as const

/** 15-minute auto-refresh interval used by both the SWR poller and the interval timer. */
export const AUTO_INTERVAL_MS = 15 * 60 * 1000
