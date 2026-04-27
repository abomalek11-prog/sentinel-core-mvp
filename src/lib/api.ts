import type {
  AnalyzeRequest,
  DemoResponse,
  HealthResponse,
  SSEEventType,
} from '@/types/sentinel';

const API_BASE = '/api';
const DIRECT_BACKEND_URL = 'https://sentinel-core-mvp-3.onrender.com/api';

async function smartFetch(path: string, options?: RequestInit) {
  // Always try the direct URL first in production to be safe, 
  // since we know it works and has CORS enabled.
  try {
    const res = await fetch(`${DIRECT_BACKEND_URL}${path}`, options);
    if (res.ok) return res;
  } catch (e) {
    console.error('[Sentinel] Direct fetch failed, trying proxy...', e);
  }
  
  return fetch(`${API_BASE}${path}`, options);
}

export async function fetchHealth(): Promise<HealthResponse> {
  try {
    const res = await smartFetch('/health');
    if (!res.ok) {
      console.error(`[Sentinel] Health check failed with status: ${res.status}`);
      throw new Error(`Health check failed: ${res.status}`);
    }
    return res.json();
  } catch (err) {
    console.error('[Sentinel] Backend is unreachable at:', `${window.location.origin}${API_BASE}/health`);
    console.error('[Sentinel] Error detail:', err);
    throw err;
  }
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
