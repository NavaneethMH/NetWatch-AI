
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '')
    .trim()
    .replace(/\/+$/, '');

export function apiUrl(path: string): string {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${apiBaseUrl}${normalizedPath}`;
}

export function telemetryWebSocketUrl(): string {
    const baseUrl = apiBaseUrl || window.location.origin;

    const websocketBase = baseUrl
        .replace(/^https:/i, 'wss:')
        .replace(/^http:/i, 'ws:');

    return `${websocketBase}/ws/telemetry`;
}
