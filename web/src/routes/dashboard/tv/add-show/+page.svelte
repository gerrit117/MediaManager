<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Button } from '$lib/components/ui/button';
	import { ChevronDown, LoaderCircle } from 'lucide-svelte';
	import * as Collapsible from '$lib/components/ui/collapsible/index.js';
	import * as RadioGroup from '$lib/components/ui/radio-group/index.js';
	import AddMediaCard from '$lib/components/add-media-card.svelte';
	import { resolve } from '$app/paths';
	import client from '$lib/api';
	import type { components } from '$lib/api/api';
	import { handleQueryNotificationToast } from '$lib/utils.ts';

	let searchTerm: string = $state('');
	let metadataProvider: 'tmdb' | 'tvdb' = $state('tmdb');
	let data: components['schemas']['MetaDataProviderSearchResult'][] | null = $state(null);
	let isSearching: boolean = $state(false);

	async function search(query: string) {
		query = query.trim();
		if (!query) return;
		isSearching = true;
		try {
			const results =
				await client.GET('/api/v1/tv/search', {
							params: {
								query: {
									query: query,
									metadata_provider: metadataProvider
								}
							}
						});
			if (results.data && results.data.length > 0) {
				handleQueryNotificationToast(results.data.length, query);
				data = results.data as components['schemas']['MetaDataProviderSearchResult'][];
			} else {
				handleQueryNotificationToast(0, query);
				data = [];
			}
		} finally {
			isSearching = false;
		}
	}
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Add TV Show - MediaManager" )}</title>
	<meta content="Add a new TV show to your MediaManager collection" name="description" />
</svelte:head>

<header class="flex h-16 shrink-0 items-center gap-2">
	<div class="flex items-center gap-2 px-4">
		<Sidebar.Trigger class="-ml-1" />
		<Separator class="mr-2 h-4" orientation="vertical" />
		<Breadcrumb.Root>
			<Breadcrumb.List>
				<Breadcrumb.Item class="hidden md:block">
					<Breadcrumb.Link href={resolve('/dashboard', {})}>MediaManager</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item class="hidden sm:block">
					<Breadcrumb.Link href={resolve('/dashboard', {})}>{mmT($mmLocale, "Home" )}</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item class="hidden sm:block">
					<Breadcrumb.Link href={resolve('/dashboard/tv', {})}>{mmT($mmLocale, "Shows" )}</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item>
					<Breadcrumb.Page>{mmT($mmLocale, "Search series" )}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>

<main class="mx-auto flex w-full min-w-0 max-w-7xl flex-1 flex-col gap-6 px-4 pb-6 sm:px-6">
	<div class="mx-auto grid w-full max-w-xl gap-5">
		<h1 class="text-2xl font-bold tracking-tight sm:text-3xl">
			{mmT($mmLocale, "Search series" )}
		</h1>
		<section>
			<Label for="search-box">{mmT($mmLocale, "Show Name" )}</Label>
			<Input
				bind:value={searchTerm}
				id="search-box"
				placeholder={mmT($mmLocale, "Show Name")}
				type="text"
				onkeydown={(e) => {
					if (e.key === 'Enter' && !isSearching) {
						search(searchTerm);
					}
				}}
			/>
			<p class="text-sm text-muted-foreground">{mmT($mmLocale, "Search for a series." )}</p>
		</section>
		<section>
			<Collapsible.Root class="w-full space-y-1">
				<Collapsible.Trigger class="flex min-h-11 w-full items-center justify-between rounded-lg border px-3 text-sm font-medium">

						<h4 class="text-sm font-semibold">{mmT($mmLocale, "Advanced Settings" )}</h4>
						<ChevronDown class="size-4" />
				</Collapsible.Trigger>
				<Collapsible.Content class="space-y-3 rounded-lg border p-3">
					<Label for="metadata-provider-selector">{mmT($mmLocale, "Choose which Metadata Provider to query." )}</Label>
					<RadioGroup.Root bind:value={metadataProvider} id="metadata-provider-selector">
						<div class="flex items-center space-x-2">
							<RadioGroup.Item id="option-one" value="tmdb" />
							<Label for="option-one">{mmT($mmLocale, "TMDB (Recommended)" )}</Label>
						</div>
						<div class="flex items-center space-x-2">
							<RadioGroup.Item id="option-two" value="tvdb" />
							<Label for="option-two">TVDB</Label>
						</div>
					</RadioGroup.Root>
				</Collapsible.Content>
			</Collapsible.Root>
		</section>
		<section>
			<Button onclick={() => search(searchTerm)} class="min-h-11 w-full" type="submit" disabled={isSearching || !searchTerm.trim()}>
				{#if isSearching}
					<LoaderCircle class="mr-2 h-4 w-4 animate-spin" />
					<span class="animate-pulse">{mmT($mmLocale, "Searching..." )}</span>
				{:else}
					{mmT($mmLocale, "Search" )}
				{/if}
			</Button>
		</section>
	</div>



	{#if data && data.length === 0}
		<h3 class="mx-auto">{mmT($mmLocale, "No Shows found." )}</h3>
	{:else if data}
		<div
			class="grid w-full auto-rows-min gap-4 grid-cols-2
		 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 2xl:grid-cols-5"
		>
			{#each data as dataItem (dataItem.external_id)}
				<AddMediaCard result={dataItem} isShow={true} />
			{/each}
		</div>
	{/if}
</main>
