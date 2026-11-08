<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import RequestCenter from '$lib/components/requests/request-center.svelte';
	import StatCard from '$lib/components/stats/stat-cards.svelte';
	import RecommendedMediaCarousel from '$lib/components/recommended-media-carousel.svelte';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import client from '$lib/api';
	import type { components } from '$lib/api/api.d.ts';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();
	let recommendedShows: components['schemas']['MetaDataProviderSearchResult'][] = $state([]);
	let showsLoading = $state(true);

	let recommendedMovies: components['schemas']['MetaDataProviderSearchResult'][] = $state([]);
	let moviesLoading = $state(true);

    let discoveryError=$state('');
    async function trending(kind:'tv'|'movie') {
        try {
            const response=await fetch('/api/v1/discover/'+kind+'?mode=trending&window=week&language='+$mmLocale);
            const payload=await response.json();
            if(!response.ok)throw Error(typeof payload.detail==='string'?payload.detail:'Discovery could not be loaded.');
            if(kind==='tv')recommendedShows=payload.results;else recommendedMovies=payload.results;
        }catch(error){discoveryError=(error as Error).message;}
        finally{if(kind==='tv')showsLoading=false;else moviesLoading=false;}
    }
    onMount(() => {
        void trending('tv');void trending('movie');

    });
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Dashboard - MediaManager" )}</title>
	<meta
		content="MediaManager Dashboard - View your recommended movies and TV shows"
		name="description"
	/>
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
				<Breadcrumb.Item>
					<Breadcrumb.Page>{mmT($mmLocale, "Home" )}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>
<div class="flex flex-1 flex-col gap-4 p-4 pt-0">
	<h1 class="scroll-m-20 text-center text-4xl font-extrabold tracking-tight lg:text-5xl">
		{mmT($mmLocale, "Overview" )}
	</h1>
	<main class="min-h-screen flex-1 items-center justify-center rounded-xl p-4 md:min-h-min">
        <RequestCenter overview={true}/>
		{#if discoveryError}<p role="alert" class="my-4 rounded-xl border border-destructive p-3 text-sm text-destructive">{mmT($mmLocale,discoveryError)}</p>{/if}
        <div class="mx-auto">
			<h3 class="my-4 text-center text-2xl font-semibold">{mmT($mmLocale, "This week: series" )}</h3>
			<RecommendedMediaCarousel isLoading={showsLoading} isShow={true} media={recommendedShows} />

			<h3 class="my-4 text-center text-2xl font-semibold">{mmT($mmLocale, "This week: movies" )}</h3>
			<RecommendedMediaCarousel
				isLoading={moviesLoading}
				isShow={false}
				media={recommendedMovies}
			/>
		</div>
	</main>
</div>
