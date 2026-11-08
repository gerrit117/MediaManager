<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
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

	let loading = $state(false);
	let errorMessage = $state<string | null>(null);
	let {
		result,
		isShow = true
	}: { result: components['schemas']['MetaDataProviderSearchResult']; isShow: boolean } = $props();

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

<Card.Root class="col-span-full flex h-full flex-col overflow-x-hidden sm:col-span-1">
	<Card.Header>
		<Card.Title class="flex h-12 items-center leading-tight">
			{result.name}
			{#if result.year != null}
				({result.year})
			{/if}
		</Card.Title>
		<Card.Description class="truncate"
			>{result.overview !== '' ? result.overview : mmT($mmLocale, "No overview available")}</Card.Description
		>
	</Card.Header>
	<Card.Content class="flex flex-1 items-center justify-center">
		{#if result.poster_path != null}
			<img
				class="aspect-[2/3] h-full w-full rounded-lg object-cover"
                loading="lazy" decoding="async"
				src={result.poster_path}
				alt="{result.name}'s Poster Image"
			/>
		{:else}
			<div class="flex h-full w-full items-center justify-center">
				<ImageOff class="h-12 w-12 text-gray-400" />
			</div>
		{/if}
	</Card.Content>
	<Card.Footer class="flex flex-col items-start gap-2 rounded-b-lg border-t bg-card p-4">
		{#if result.added}
			<Button
				class="h-auto min-h-9 w-full whitespace-normal text-center text-xs font-semibold sm:text-sm"
				variant="secondary"
				href={resolve(
					isShow ? '/dashboard/tv/[showId]' : '/dashboard/movies/[movieId]',
					isShow ? { showId: result.id ?? '' } : { movieId: result.id ?? '' }
				)}
			>
				{mmT($mmLocale, isShow ? "Series already exists" : "Movie already exists")}
			</Button>
		{:else if !currentUser?.()?.is_superuser}
            <RequestMediaDialog {result} {isShow}/>
		{:else}
			<Button class="h-auto min-h-9 w-full whitespace-normal text-center text-xs font-semibold sm:text-sm" disabled={loading} onclick={() => addMedia()}>
				{#if loading}
					<LoaderCircle class="mr-2 h-4 w-4 animate-spin" />
					<span class="animate-pulse">{mmT($mmLocale, "Loading..." )}</span>
				{:else}
					{mmT($mmLocale, isShow ? "Add series" : "Add movie")}
				{/if}
			</Button>
		{/if}
		<div class="flex w-full items-center gap-2">
			{#if result.vote_average != null}
				<span class="flex items-center text-sm font-medium text-yellow-600">
					<svg class="mr-1 h-4 w-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20"
						><path
							d="M10 15l-5.878 3.09 1.122-6.545L.488 6.91l6.561-.955L10 0l2.951 5.955 6.561.955-4.756 4.635 1.122 6.545z"
						/></svg
					>
					{mmT($mmLocale, "Rating:" )} {Math.round(result.vote_average)}/10
				</span>
			{/if}
		</div>
		{#if errorMessage}
			<p role="alert" class="w-full rounded bg-red-50 px-2 py-1 text-xs text-red-500">{mmT($mmLocale, errorMessage)}</p>
		{/if}
	</Card.Footer>
</Card.Root>
