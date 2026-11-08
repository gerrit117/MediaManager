<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Button } from '$lib/components/ui/button';
	import { toast } from 'svelte-sonner';
	import { Badge } from '$lib/components/ui/badge';

	import * as Table from '$lib/components/ui/table';
	import client from '$lib/api';
	import type { components } from '$lib/api/api';
	import SelectFilePathSuffixDialog from '$lib/components/download-dialogs/select-file-path-suffix-dialog.svelte';
	import { invalidateAll } from '$app/navigation';
	import TorrentTable from '$lib/components/download-dialogs/torrent-table.svelte';
	import SearchTabs from '$lib/components/download-dialogs/search-tabs.svelte';
	import DownloadDialogWrapper from '$lib/components/download-dialogs/download-dialog-wrapper.svelte';

	let { movie }: { movie: components['schemas']['Movie'] } = $props();
	let dialogueState = $state(false);
	let torrentsError: string | null = $state(null);
	let queryOverride: string = $state('');
	let filePathSuffix: string = $state('');

	let torrentsPromise: any = $state(null);
	let torrentsData: any[] | null = $state(null);
	let tabState: string = $state('basic');
	let isLoading: boolean = $state(false);

	let advancedMode: boolean = $derived(tabState === 'advanced');

	const tableColumnHeadings = [
		{ name: 'Size', id: 'size' },
		{ name: 'Downloadart', id: 'usenet' },
		{ name: 'Seeders', id: 'seeders' },
		{ name: 'Score', id: 'score' },
		{ name: 'Indexer', id: 'indexer' },
		{ name: 'Indexer Flags', id: 'flags' }
	];

	async function downloadTorrent(result_id: string) {
		torrentsError = null;
		const { data, response, error } = await client.POST(`/api/v1/movies/{movie_id}/torrents`, {
			params: {
				path: {
					movie_id: movie.id!
				},
				query: {
					public_indexer_result_id: result_id,
					override_file_path_suffix: filePathSuffix === '' ? undefined : filePathSuffix
				}
			}
		});
		if (response.status === 409) {
			const errorMessage = `There already is a Movie File using the Filepath Suffix '${filePathSuffix}'. Try again with a different Filepath Suffix.`;
			console.warn(errorMessage);
			torrentsError = errorMessage;
			if (dialogueState) toast.info(mmT($mmLocale,errorMessage));
		} else if (!response.ok) {
			const errorMessage = (error as { detail?: string } | undefined)?.detail ?? `Downloadmanager-Anfrage fehlgeschlagen: ${response.statusText}`;
			console.error(errorMessage);
			torrentsError = errorMessage;
			toast.error(mmT($mmLocale,errorMessage));
		} else {
			console.log('Download submitted:', data);
			toast.success(mmT($mmLocale,'Download an den Downloadmanager übergeben.'));
		}
		await invalidateAll();
	}

	async function search() {
		isLoading = true;
		torrentsError = null;
		torrentsData = null;
		torrentsPromise = client
			.GET('/api/v1/movies/{movie_id}/torrents', {
				params: {
					query: {
						search_query_override: advancedMode ? queryOverride : undefined
					},
					path: {
						movie_id: movie.id!
					}
				}
			})
			.then((data) => data?.data)
			.finally(() => (isLoading = false));
		toast.info(mmT($mmLocale,'Searching indexers...'));

		torrentsData = await torrentsPromise;
		toast.info(mmT($mmLocale,'Found ' + torrentsData?.length + ' releases.'));
	}
</script>

<DownloadDialogWrapper
	bind:open={dialogueState}
	triggerText={mmT($mmLocale, "Download Movie")}
	title={mmT($mmLocale, "Download a Movie")}
	description={mmT($mmLocale, "Search indexers and send releases to your download manager for this movie.")}
>
	<SearchTabs
		bind:tabState
		{isLoading}
		bind:queryOverride
		onSearch={search}
		advancedModeHelpText="The custom query will override the default search string like 'A Minecraft Movie (2025)'."
	>
		{#snippet basicModeContent()}
			<Button disabled={isLoading} class="w-fit" onclick={search}>{mmT($mmLocale, "Search indexers" )}</Button>
		{/snippet}
	</SearchTabs>
	{#if torrentsError}
		<div class="my-2 w-full text-center text-red-500">{mmT($mmLocale, "An error occurred:" )} {mmT($mmLocale, torrentsError)}</div>
	{/if}
	<TorrentTable {torrentsPromise} columns={tableColumnHeadings}>
		{#snippet rowSnippet(torrent)}
			<Table.Cell data-label={mmT($mmLocale, "Title")} class="font-medium">{torrent.title}</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Size")}>{(torrent.size / 1024 / 1024 / 1024).toFixed(2)}GB</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Download type")}>{torrent.usenet ? 'Usenet / NZB' : 'Torrent'}</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Seeders")}>{torrent.usenet ? '—' : torrent.seeders}</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Score")}>{torrent.score}</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Indexer")}>{torrent.indexer ?? mmT($mmLocale, "Unknown")}</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Indexer Flags")}>
				{#each (torrent.flags ?? []) as flag (flag)}
					<Badge variant="outline">{flag}</Badge>
				{/each}
			</Table.Cell>
			<Table.Cell data-label={mmT($mmLocale, "Actions")} class="text-right">
				<SelectFilePathSuffixDialog
					media={movie}
					bind:filePathSuffix
					callback={() => downloadTorrent(torrent.id)}
				/>
			</Table.Cell>
		{/snippet}
	</TorrentTable>
</DownloadDialogWrapper>
