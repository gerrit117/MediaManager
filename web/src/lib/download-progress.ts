import { env } from '$env/dynamic/public';

export type DownloadProgress = { percent: number | null; state: string; client: string; usenet: boolean; phase?: string; imported?: boolean };
let cached: Record<string, DownloadProgress> = {};
let expires = 0;
let pending: Promise<Record<string, DownloadProgress>> | null = null;

export function loadDownloadProgress(): Promise<Record<string, DownloadProgress>> {
	if (pending) return pending;
	if (Date.now() < expires) return Promise.resolve(cached);
	pending = fetch(`${env.PUBLIC_API_URL ?? ''}/api/v1/torrent/progress`, { credentials: 'include' })
		.then(async (response) => response.ok ? await response.json() : {})
		.catch(() => ({}))
		.then((value) => { cached = value; expires = Date.now() + 4000; return cached; })
		.finally(() => { pending = null; });
	return pending;
}
