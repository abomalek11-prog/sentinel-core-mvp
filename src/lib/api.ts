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
    : '';

async function smartFetch(path: string, options?: RequestInit) {
  const url = `${BACKEND_URL}${path}`;
  return fetch(url, options);
}

async function fetchWithFallback(paths: string[], options?: RequestInit) {
  let lastError: Error | null = null;

  for (const path of paths) {
    try {
      const res = await smartFetch(path, options);
      if (!res.ok) {
        lastError = new Error(`Request failed (${path}): ${res.status}`);
        continue;
      }
      return res;
    } catch (err) {
      lastError = err as Error;
    }
  }

  throw lastError ?? new Error('Request failed');
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetchWithFallback(['/api/health', '/health'], { cache: 'no-store' });
  return res.json();
}

export async function fetchDemo(): Promise<DemoResponse> {
  const res = await fetchWithFallback(['/api/demo', '/demo']);
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
      const res = await fetchWithFallback(['/api/analyze/stream', '/analyze/stream'], {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

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
