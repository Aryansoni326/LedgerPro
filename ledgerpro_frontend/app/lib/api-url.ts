/**
 * API base URL for fetch calls.
 * - Local Docker/dev: http://localhost:8000 when env is unset
 * - Production: set NEXT_PUBLIC_API_URL to your deployed API URL
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured !== undefined && configured !== '') {
    return configured.replace(/\/$/, '');
  }
  return 'http://localhost:8000';
}
