<script lang="ts">
	import AppSidebar from '$lib/components/nav/app-sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import type { LayoutProps } from './$types';
	import { onMount, setContext } from 'svelte';
	import { env } from '$env/dynamic/public';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';
	import client from '$lib/api';
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

	if (data.user?.is_superuser) {
		client.GET('/api/v1/movies/importable').then(({ data, error }) => {
			if (!error) {
				importableMovies = data;
			}
		});
		client.GET('/api/v1/tv/importable').then(({ data, error }) => {
			if (!error) {
				importableShows = data;
			}
		});
	}
</script>

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset>
		{@render children()}
	</Sidebar.Inset>
</Sidebar.Provider>
