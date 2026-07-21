/**
 * API base URL for fetch calls.
 * - Local Docker/dev: http://localhost:8000 (default when env unset)
 * - Single Vercel project: leave NEXT_PUBLIC_API_URL unset in production → same origin ("")
 * - Or set NEXT_PUBLIC_API_URL=https://your-app.vercel.app explicitly
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured !== undefined) {
    return configured.replace(/\/$/, '');
  }
  if (process.env.NODE_ENV === 'production') {
    return '';
  }
  return 'http://localhost:8000';
}
