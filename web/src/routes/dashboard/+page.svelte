<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import StatCard from '$lib/components/stats/stat-cards.svelte';
	import RecommendedMediaCarousel from '$lib/components/recommended-media-carousel.svelte';
	import { resolve } from '$app/paths';
    let libraryCounts=$state<{movies:number;shows:number}|null>(null);
    async function refreshCounts(){try{const r=await fetch('/api/v1/library/summary');if(r.ok)libraryCounts=await r.json();}catch{}}
	import { onMount } from 'svelte';
	import client from '$lib/api';
	import type { components } from '$lib/api/api.d.ts';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();
	let recommendedShows: components['schemas']['MetaDataProviderSearchResult'][] = $state([]);
	let showsLoading = $state(true);

	let recommendedMovies: components['schemas']['MetaDataProviderSearchResult'][] = $state([]);
	let moviesLoading = $state(true);

	onMount(() => {
		client.GET('/api/v1/tv/recommended').then((res) => {
			recommendedShows = res.data as components['schemas']['MetaDataProviderSearchResult'][];
			showsLoading = false;
		});
		client.GET('/api/v1/movies/recommended').then((res) => {
			recommendedMovies = res.data as components['schemas']['MetaDataProviderSearchResult'][];
			moviesLoading = false;
		});
        void refreshCounts();const timer=setInterval(refreshCounts,10000);return()=>clearInterval(timer);
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
		{mmT($mmLocale, "Dashboard" )}
	</h1>
	<main class="min-h-screen flex-1 items-center justify-center rounded-xl p-4 md:min-h-min">
		<div class="mx-auto">
			<div class="my-8 block text-2xl">{mmT($mmLocale, "Welcome to MediaManager!" )}</div>
			<StatCard showCount={libraryCounts?.shows ?? data.tvShows?.length ?? 0} moviesCount={libraryCounts?.movies ?? data.movies?.length ?? 0}
			></StatCard>
		</div>
		<div class="mx-auto">
			<h3 class="my-4 text-center text-2xl font-semibold">{mmT($mmLocale, "Trending Shows" )}</h3>
			<RecommendedMediaCarousel isLoading={showsLoading} isShow={true} media={recommendedShows} />

			<h3 class="my-4 text-center text-2xl font-semibold">{mmT($mmLocale, "Trending Movies" )}</h3>
			<RecommendedMediaCarousel
				isLoading={moviesLoading}
				isShow={false}
				media={recommendedMovies}
			/>
		</div>
	</main>
</div>
