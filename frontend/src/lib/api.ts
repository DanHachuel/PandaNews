const BASE = '/api/v1';

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 204) {
    return undefined as T;
  }
  if (!res.ok) {
    let detail = `Erro HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(BASE + path).then((r) => handle<T>(r));
}

export function apiSend<T>(
  path: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
): Promise<T> {
  return fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => handle<T>(r));
}
