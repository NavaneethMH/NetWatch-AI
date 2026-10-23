/**
 * Utility to retrieve operator API key stored in sessionStorage for browser operations.
 * If not present, returns null. Never stores secrets in bundles or build variables.
 */
export function getOperatorKey(): string | null {
  try {
    return sessionStorage.getItem('netwatch_operator_key');
  } catch {
    return null;
  }
}

export function setOperatorKey(key: string): void {
  try {
    sessionStorage.setItem('netwatch_operator_key', key);
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function getAuthHeaders(): HeadersInit {
  const key = getOperatorKey();
  if (key) {
    return { 'X-NetWatch-Key': key };
  }
  return {};
}
