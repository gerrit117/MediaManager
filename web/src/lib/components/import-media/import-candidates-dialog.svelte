<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Button, buttonVariants } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { toast } from 'svelte-sonner';
	import client from '$lib/api';
	import type { components } from '$lib/api/api';
	import { Spinner } from '$lib/components/ui/spinner';
	import SuggestedMediaCard from '$lib/components/import-media/suggested-media-card.svelte';
	import { invalidateAll } from '$app/navigation';

	let {
		isTv,
		name,
		candidates,
		children
	}: {
		isTv: boolean;
		name: string;
		candidates: components['schemas']['MetaDataProviderSearchResult'][];
		children: any;
	} = $props();
	let dialogOpen = $state(false);
	let submitRequestError = $state<string | null>(null);
	let isImporting = $state<boolean>(false);
	let searchQuery = $state('');
	let searchProvider = $state<'tmdb' | 'tvdb'>('tmdb');
	let searchResults = $state<components['schemas']['MetaDataProviderSearchResult'][] | null>(null);
	let searchError = $state<string | null>(null);
	let isSearching = $state(false);
	$effect(() => {
		if (!dialogOpen) { searchResults = null; searchQuery = ''; searchError = null; }
	});
	async function handleManualSearch() {
		if (!searchQuery.trim() || isSearching) return;
		isSearching = true; searchError = null;
		try {
			const endpoint = isTv ? '/api/v1/tv/search' : '/api/v1/movies/search';
			const { data, error } = await client.GET(endpoint, { params: { query: { query: searchQuery.trim(), metadata_provider: searchProvider } } });
			if (error) { searchError = 'Metadatensuche fehlgeschlagen. Bitte erneut versuchen.'; return; }
			searchResults = data ?? [];
		} catch { searchError = 'Metadatensuche nicht erreichbar. Bitte erneut versuchen.'; }
		finally { isSearching = false; }
	}

	async function handleImportMedia(media: components['schemas']['MetaDataProviderSearchResult']) {
		isImporting = true;
		submitRequestError = null;
		let errored = null;
		if (isTv) {
			let { data } = await client.POST('/api/v1/tv/shows', {
				params: {
					query: {
						metadata_provider: media.metadata_provider as 'tmdb' | 'tvdb',
						show_id: media.external_id
					}
				}
			});
			let showId = data?.id ?? 'no_id';
			const { error } = await client.POST('/api/v1/tv/importable/{show_id}', {
				params: {
					path: {
						show_id: showId
					},
					query: {
						directory: name
					}
				}
			});
			errored = error;
		} else {
			let { data } = await client.POST('/api/v1/movies', {
				params: {
					query: {
						metadata_provider: media.metadata_provider as 'tmdb' | 'tvdb',
						movie_id: media.external_id
					}
				}
			});
			let movieId = data?.id ?? 'no_id';
			const { error } = await client.POST('/api/v1/movies/importable/{movie_id}', {
				params: {
					path: {
						movie_id: movieId
					},
					query: {
						directory: name
					}
				}
			});
			errored = error;
		}
		isImporting = false;

		if (errored) {
			toast.error(mmT($mmLocale,'Failed to import'));
		} else {
			toast.success(mmT($mmLocale,'Imported successfully!'));
		}
		await invalidateAll();
		dialogOpen = false;
	}
</script>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger
		class={buttonVariants({ variant: 'default' })}
		onclick={() => {
			dialogOpen = true;
		}}
	>
		{@render children?.()}
	</Dialog.Trigger>
	<Dialog.Content class="max-h-[90vh] w-[calc(100vw-2rem)] max-w-6xl min-w-0 overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{mmT($mmLocale, "Import unknown" )} {isTv ? 'show' : 'movie'} "{name}"</Dialog.Title>
			<Dialog.Description
				>{mmT($mmLocale, "Select the" )} {isTv ? 'show' : 'movie'} {mmT($mmLocale, "that is in this directory to import it!" )}
			</Dialog.Description>
		</Dialog.Header>
		<div
			class="grid w-full auto-rows-min gap-4 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
		>
			{#if !isImporting}
				{#each (searchResults ?? candidates) as candidate (candidate.metadata_provider + ":" + candidate.external_id)}
					<SuggestedMediaCard result={candidate} action={() => handleImportMedia(candidate)}
					></SuggestedMediaCard>
				{:else}
					{mmT($mmLocale, "Kein passender Titel gefunden. Du kannst unten manuell suchen." )}
				{/each}
			{:else}
				<Spinner class="size-8"></Spinner>
			{/if}
			{#if submitRequestError}
				<p class="col-span-full text-center text-sm text-red-500">{mmT($mmLocale, submitRequestError)}</p>
			{/if}
		</div>
		<form class="flex min-w-0 flex-col gap-2 border-t pt-4 sm:flex-row" onsubmit={(event) => { event.preventDefault(); void handleManualSearch(); }}>
			<input aria-label={mmT($mmLocale, "Titel manuell suchen")} class="min-w-0 flex-1 rounded-md border bg-background px-3 py-2" placeholder={mmT($mmLocale, "Titel manuell suchen")} bind:value={searchQuery} />
			<select aria-label={mmT($mmLocale, "Metadatenanbieter")} class="rounded-md border bg-background px-3 py-2" bind:value={searchProvider}><option value="tmdb">TMDB</option><option value="tvdb">TVDB</option></select>
			<Button type="submit" disabled={isSearching || isImporting || !searchQuery.trim()}>{isSearching ? 'Sucht …' : mmT($mmLocale, "Titel suchen")}</Button>
		</form>
		{#if searchError}<p role="alert" class="text-sm text-destructive">{mmT($mmLocale, searchError)}</p>{/if}
		<Dialog.Footer>
			<Button disabled={isImporting} onclick={() => (dialogOpen = false)} variant="outline"
				>{mmT($mmLocale, "Cancel" )}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
