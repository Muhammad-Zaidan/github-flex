export function compact(n) {
  if (n == null) return '—';
  if (n < 1000) return String(n);
  if (n < 1e6) return `${(n / 1000).toFixed(n < 1e4 ? 1 : 0).replace(/\.0$/, '')}k`;
  return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
}

export function yearsSince(iso) {
  const y = (Date.now() - new Date(iso)) / (365.25 * 864e5);
  return y < 1 ? `${Math.max(1, Math.round(y * 12))}mo` : `${y.toFixed(y < 10 ? 1 : 0).replace(/\.0$/, '')}y`;
}
