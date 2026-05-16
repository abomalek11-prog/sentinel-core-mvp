import type {
  AnalyzeRequest,
  DemoResponse,
  HealthResponse,
  SSEEventType,
} from '@/types/sentinel';

const BACKEND_URL =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : (process.env.NEXT_PUBLIC_API_URL ?? 'https://sentinel-core-mvp-3.onrender.com');

async function smartFetch(path: string, options?: RequestInit) {
  const url = `${BACKEND_URL}${path}`;
  return fetch(url, options);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const paths = ['/health', '/api/health'];
  let lastError: Error | null = null;

  for (const path of paths) {
    try {
      const res = await smartFetch(path, { cache: 'no-store' });
      if (!res.ok) {
        lastError = new Error(`Health check failed (${path}): ${res.status}`);
        continue;
      }
      return res.json();
    } catch (err) {
      lastError = err as Error;
    }
  }

  throw lastError ?? new Error('Health check failed');
}

export async function fetchDemo(): Promise<DemoResponse> {
  const res = await smartFetch('/demo');
  if (!res.ok) throw new Error(`Demo fetch failed: ${res.status}`);
  return res.json();
}

export type SSEHandler = (event: SSEEventType, data: unknown) => void;

export function streamAnalysis(
  request: AnalyzeRequest,
  onEvent: SSEHandler,
  onError: (err: Error) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await smartFetch('/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`Analysis request failed: ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent: SSEEventType | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim() as SSEEventType;
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6));
              onEvent(currentEvent, data);
            } catch {
              // skip malformed data
            }
            currentEvent = null;
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError(err as Error);
      }
    }
  })();

  return controller;
}
