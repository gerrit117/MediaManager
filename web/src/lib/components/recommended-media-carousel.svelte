<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import AddMediaCard from '$lib/components/add-media-card.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import { Button } from '$lib/components/ui/button';
	import { ChevronRight } from 'lucide-svelte';
	import type { components } from '$lib/api/api';
	import { resolve } from '$app/paths';

	let {
		media,
		isShow,
		isLoading
	}: {
		media: components['schemas']['MetaDataProviderSearchResult'][];
		isShow: boolean;
		isLoading: boolean;
	} = $props();
</script>

<div
	class="grid w-full gap-4 sm:grid-cols-1
     md:grid-cols-2 lg:grid-cols-3"
>
	{#if isLoading}
		<Skeleton class="h-[70vh] w-full" />
		<Skeleton class="h-[70vh] w-full" />
		<Skeleton class="h-[70vh] w-full" />
	{:else}
		{#each media.slice(0, 3) as mediaItem (mediaItem.external_id)}
			<AddMediaCard {isShow} result={mediaItem} />
		{/each}
	{/if}
	{#if isShow}
		<Button class="md:col-start-2" variant="secondary" href={resolve('/dashboard/tv/add-show', {})}>
			{mmT($mmLocale, "More recommendations" )}
			<ChevronRight />
		</Button>
	{:else}
		<Button
			class="md:col-start-2"
			variant="secondary"
			href={resolve('/dashboard/movies/add-movie', {})}
		>
			{mmT($mmLocale, "More recommendations" )}
			<ChevronRight />
		</Button>
	{/if}
</div>
