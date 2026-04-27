import type {
  AnalyzeRequest,
  DemoResponse,
  HealthResponse,
  SSEEventType,
} from '@/types/sentinel';

const API_BASE = '/api';

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function fetchDemo(): Promise<DemoResponse> {
  const res = await fetch(`${API_BASE}/demo`);
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
      const res = await fetch(`${API_BASE}/analyze/stream`, {
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
