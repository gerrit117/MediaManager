<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import MediaPreviewDialog from '$lib/components/media-preview-dialog.svelte';
	import {getContext} from 'svelte';
    import RequestMediaDialog from '$lib/components/requests/request-media-dialog.svelte';
    const currentUser=getContext<()=>any>('user');
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { ImageOff, LoaderCircle } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { components } from '$lib/api/api';
	import client from '$lib/api';

	let previewOpen = $state(false);
	let loading = $state(false);
	let errorMessage = $state<string | null>(null);
	let {
		result,
		isShow = true
	}: { result: components['schemas']['MetaDataProviderSearchResult']; isShow: boolean } = $props();

    function showPreview() { errorMessage=null; previewOpen=true; }

    async function addMedia() {
        loading=true;errorMessage=null;
        try {
            let response;
            if(isShow){
                response=await client.POST('/api/v1/tv/shows',{params:{query:{show_id:result.external_id,metadata_provider:result.metadata_provider as 'tmdb'|'tvdb',language:$mmLocale}}});
            }else{
                response=await client.POST('/api/v1/movies',{params:{query:{movie_id:result.external_id,metadata_provider:result.metadata_provider as 'tmdb'|'tvdb',language:$mmLocale}}});
            }
            if(!response.response.ok||!response.data?.id)throw Error(typeof (response.error as any)?.detail==='string'?(response.error as any).detail:'The title could not be added. Please try again.');
            const id=response.data.id;
            await goto(resolve(isShow?'/dashboard/tv/[showId]':'/dashboard/movies/[movieId]',isShow?{showId:id}:{movieId:id}),{invalidateAll:true});
        }catch(error){errorMessage=(error as Error).message;}
        finally{loading=false;}
    }
</script>

<Card.Root data-media-card class="min-w-0 flex h-full flex-col overflow-hidden">
	<Card.Header class="shrink-0 p-3 sm:p-5">
		<Card.Title class="h-12 text-sm leading-6 sm:text-base">
			<button type="button" class="line-clamp-2 h-12 w-full text-left leading-6 hover:underline focus-visible:underline" onclick={showPreview}>{result.name}{result.year != null ? ` (${result.year})` : ''}</button>
		</Card.Title>
		<Card.Description class="hidden h-5 truncate sm:block"
			>{result.overview ? result.overview : mmT($mmLocale, "No overview available")}</Card.Description
		>
	</Card.Header>
	<Card.Content class="shrink-0 px-3 pb-3 sm:px-5 sm:pb-5">
		<button type="button" class="relative block aspect-[2/3] w-full overflow-hidden rounded-lg focus-visible:ring-2 focus-visible:ring-ring" aria-label={mmT($mmLocale,"Show details")+": "+result.name} onclick={showPreview}>
		{#if result.poster_path != null}
			<img
				class="absolute inset-0 h-full w-full object-cover"
                loading="lazy" decoding="async"
				src={result.poster_path}
				alt="{result.name}'s Poster Image"
			/>
		{:else}
			<div class="absolute inset-0 flex items-center justify-center bg-muted">
				<ImageOff class="h-12 w-12 text-gray-400" />
			</div>
		{/if}
		</button>
	</Card.Content>
	<Card.Footer class="mt-auto flex flex-col items-start gap-2 rounded-b-lg border-t bg-card p-3 sm:p-4">
		<Button variant="outline" class="h-11 w-full text-sm" onclick={showPreview}>{mmT($mmLocale,"Show details")}</Button>
		{#if result.added}
			<Button
				class="h-14 min-h-14 w-full whitespace-normal text-center text-xs font-semibold leading-tight sm:text-sm"
				variant="secondary"
				href={resolve(
					isShow ? '/dashboard/tv/[showId]' : '/dashboard/movies/[movieId]',
					isShow ? { showId: result.id ?? '' } : { movieId: result.id ?? '' }
				)}
			>
				{mmT($mmLocale, isShow ? "Series already exists" : "Movie already exists")}
			</Button>
		{:else if !currentUser?.()?.is_superuser}
            <RequestMediaDialog {result} {isShow} triggerClass="h-14 min-h-14 leading-tight"/>
		{:else}
			<Button class="h-14 min-h-14 w-full whitespace-normal text-center text-xs font-semibold leading-tight sm:text-sm" disabled={loading} onclick={() => addMedia()}>
				{#if loading}
					<LoaderCircle class="mr-2 h-4 w-4 animate-spin" />
					<span class="animate-pulse">{mmT($mmLocale, "Loading..." )}</span>
				{:else}
					{mmT($mmLocale, isShow ? "Add series" : "Add movie")}
				{/if}
			</Button>
		{/if}
		<div class="flex h-5 w-full items-center gap-2">
			{#if result.vote_average != null}
				<span class="flex items-center text-sm font-medium text-yellow-600">
					<svg class="mr-1 h-4 w-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20"
						><path
							d="M10 15l-5.878 3.09 1.122-6.545L.488 6.91l6.561-.955L10 0l2.951 5.955 6.561.955-4.756 4.635 1.122 6.545z"
						/></svg
					>
					{mmT($mmLocale, "Rating:" )} {result.vote_average.toLocaleString($mmLocale,{maximumFractionDigits:1})}/10
				</span>
			{/if}
		</div>
		{#if errorMessage}
			<p role="alert" class="w-full rounded bg-red-50 px-2 py-1 text-xs text-red-500">{mmT($mmLocale, errorMessage)}</p>
		{/if}
	</Card.Footer>
</Card.Root>

<MediaPreviewDialog bind:open={previewOpen} {result} {isShow} onAdd={addMedia} adding={loading} addError={errorMessage}/>
