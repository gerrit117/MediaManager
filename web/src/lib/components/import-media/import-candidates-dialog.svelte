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
	import { getContext } from 'svelte';
	const scan = getContext<{remove:(kind:'movies'|'tv',directory:string)=>void}>('libraryScan');
	let importMode = $state<'catalogue'|'reorganize'>('catalogue');

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
		if (!dialogOpen) { importMode = 'catalogue'; searchResults = null; searchQuery = ''; searchError = null; }
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
        if (importMode === 'reorganize' && !confirm(mmT($mmLocale,'Reorganize this directory? Files will be renamed and copied or linked into the configured library structure.'))) return;
		isImporting = true;
		submitRequestError = null;
		let errored = null;
        try {
		if (isTv) {
			let { data } = await client.POST('/api/v1/tv/shows', {
				params: {
					query: {
						metadata_provider: media.metadata_provider as 'tmdb' | 'tvdb',
						show_id: media.external_id
					}
				}
			});
			if (!data?.id) throw new Error('Failed to import');
            let showId = data.id;
			const { error } = await client.POST('/api/v1/tv/importable/{show_id}', {
				params: {
					path: {
						show_id: showId
					},
					query: {
						directory: name,
                        mode: importMode
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
			if (!data?.id) throw new Error('Failed to import');
            let movieId = data.id;
			const { error } = await client.POST('/api/v1/movies/importable/{movie_id}', {
				params: {
					path: {
						movie_id: movieId
					},
					query: {
						directory: name,
                        mode: importMode
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
            scan?.remove(isTv ? 'tv':'movies',name);
		}
        if (!errored) { await invalidateAll(); dialogOpen = false; }
        else submitRequestError = typeof errored === 'object' && errored && 'detail' in errored ? String(errored.detail) : 'Failed to import';
        } catch { submitRequestError = 'Failed to import'; toast.error(mmT($mmLocale,'Failed to import')); }
        finally { isImporting = false; }
	}
</script>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger
		class={buttonVariants({ variant: 'default' })}
		onclick={() => {
			dialogOpen = true;
            if (!candidates.length) {
                searchQuery = (name.split('/').pop() ?? '').replace(/\[[^\]]+\]/g, '').replace(/[._]/g, ' ').trim();
                void handleManualSearch();
            }
		}}
	>
		{@render children?.()}
	</Dialog.Trigger>
	<Dialog.Content class="max-h-[90vh] w-[calc(100vw-2rem)] max-w-6xl min-w-0 overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{mmT($mmLocale, isTv ? "Import existing show" : "Import existing movie")} — {name}</Dialog.Title>
			<Dialog.Description
				>{mmT($mmLocale,"Select the matching title and import mode for this directory.")}
			</Dialog.Description>
		</Dialog.Header>
        <label class="block space-y-2 font-medium">{mmT($mmLocale,'Import mode')}
            <select aria-label={mmT($mmLocale,'Import mode')} class="w-full rounded-md border bg-background p-3" bind:value={importMode} disabled={isImporting}>
                <option value="catalogue">{mmT($mmLocale,'Catalogue only (keep files in place)')}</option>
                <option value="reorganize">{mmT($mmLocale,'Reorganize into library folders')}</option>
            </select>
        </label>
        <p class="text-sm text-muted-foreground">{mmT($mmLocale,importMode === 'catalogue' ? 'Records existing video files without moving, renaming or extracting archives.' : 'Uses the existing import process, including archive extraction and folder renaming.')}</p>
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
			<Button type="submit" disabled={isSearching || isImporting || !searchQuery.trim()}>{isSearching ? mmT($mmLocale,'Scanning…') : mmT($mmLocale, "Titel suchen")}</Button>
		</form>
		{#if searchError}<p role="alert" class="text-sm text-destructive">{mmT($mmLocale, searchError)}</p>{/if}
		<Dialog.Footer>
			<Button disabled={isImporting} onclick={() => (dialogOpen = false)} variant="outline"
				>{mmT($mmLocale, "Cancel" )}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
