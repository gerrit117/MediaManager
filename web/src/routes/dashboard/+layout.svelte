<script lang="ts">
	import AppSidebar from '$lib/components/nav/app-sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import type { LayoutProps } from './$types';
	import { onMount, setContext } from 'svelte';
	import { env } from '$env/dynamic/public';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';
	import type { components } from '$lib/api/api';

	let { data, children }: LayoutProps = $props();
	let importableShows: components['schemas']['MediaImportSuggestion'][] = $state([]);
	let importableMovies: components['schemas']['MediaImportSuggestion'][] = $state([]);
	setContext('user', () => data.user);
	setContext('importableMovies', () => importableMovies);
	setContext('importableShows', () => importableShows);

	onMount(() => {
		if (data.user?.is_superuser) {
			fetch(`${env.PUBLIC_API_URL ?? ''}/api/v1/indexers/categories`, {
				credentials: 'include'
			}).catch(() => {});
		}
	});

	if (!data.user?.is_verified) {
		toast.info('Your account requires verification. Redirecting...');
		goto(resolve('/login/verify', {}));
	}

	let scanning = $state({ movies: false, tv: false });
	let scanStatus = $state({ movies: '', tv: '' });
	async function scanLibrary(kind: 'movies' | 'tv') {
		if (!data.user?.is_superuser || scanning[kind]) return;
		scanning[kind] = true; scanStatus[kind] = 'Scanning library…';
		try {
			const response = await fetch(`${env.PUBLIC_API_URL ?? ''}/api/v1/${kind}/importable?discover_only=true`, { credentials: 'include' });
            if (!response.ok) throw new Error();
            const found: components['schemas']['MediaImportSuggestion'][] = await response.json();
			if (kind === 'movies') importableMovies = found; else importableShows = found;
			scanStatus[kind] = found.length ? 'Select a directory below to match and import.' : 'No new directories found.';
		} catch { scanStatus[kind] = 'Library scan failed. Check paths, permissions and metadata settings.'; }
		finally { scanning[kind] = false; }
	}
	setContext('libraryScan', { run: scanLibrary, busy: (kind: 'movies'|'tv') => scanning[kind], status: (kind: 'movies'|'tv') => scanStatus[kind], remove: (kind: 'movies'|'tv', directory: string) => {
		if (kind === 'movies') importableMovies = importableMovies.filter(x => x.directory !== directory);
		else importableShows = importableShows.filter(x => x.directory !== directory);
	} });

</script>

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset>
		{@render children()}
	</Sidebar.Inset>
</Sidebar.Provider>
