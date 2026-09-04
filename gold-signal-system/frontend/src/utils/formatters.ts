/**
 * Utility helpers — Phase 1 stubs.
 * Add formatting, date, number utilities as the project grows.
 */

/** Format a UTC ISO string to a localised datetime string. */
export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

/** Round a number to the given decimal places. */
export function round(value: number, decimals = 2): number {
  return Math.round(value * 10 ** decimals) / 10 ** decimals
}
