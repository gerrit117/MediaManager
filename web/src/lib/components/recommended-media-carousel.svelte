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
	class="grid w-full grid-cols-2 gap-3 lg:grid-cols-4"
>
	{#if isLoading}
		<Skeleton class="aspect-[2/3] w-full" />
		<Skeleton class="aspect-[2/3] w-full" />
		<Skeleton class="aspect-[2/3] w-full" />
	{:else}
		{#each media.slice(0, 4) as mediaItem (mediaItem.external_id)}
			<AddMediaCard {isShow} result={mediaItem} />
		{/each}
	{/if}
	{#if isShow}
		<Button class="col-span-full min-h-11" variant="secondary" href={resolve('/dashboard/tv/discover', {})}>
			{mmT($mmLocale, "Discover more" )}
			<ChevronRight />
		</Button>
	{:else}
		<Button
			class="col-span-full min-h-11"
			variant="secondary"
			href={resolve('/dashboard/movies/discover', {})}
		>
			{mmT($mmLocale, "Discover more" )}
			<ChevronRight />
		</Button>
	{/if}
</div>
