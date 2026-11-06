<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import { getFullyQualifiedMediaName } from '$lib/utils';
	import MediaLibrary from '$lib/components/media-library.svelte';
	import { resolve } from '$app/paths';
	import type { components } from '$lib/api/api.d.ts';
	import ImportCandidatesDialog from '$lib/components/import-media/import-candidates-dialog.svelte';
	import DetectedMediaCard from '$lib/components/import-media/detected-media-card.svelte';
	import { getContext,onMount } from 'svelte';
	import type { PageProps } from './$types';
	import LoadingBar from '$lib/components/loading-bar.svelte';
	import LibraryScan from '$lib/components/import-media/library-scan.svelte';

	let { data }: PageProps = $props();
    let match=$state('');let limit=$state(40);
    const scanner=getContext<{run:(kind:'movies'|'tv')=>Promise<void>}>('libraryScan');
    onMount(()=>{match=new URLSearchParams(location.search).get('match')??'';if(match)void scanner.run('movies');});

	let importableMovies: () => components['schemas']['MediaImportSuggestion'][] =
		getContext('importableMovies');
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Movies - MediaManager" )}</title>
	<meta content="Browse and manage your movie collection in MediaManager" name="description" />
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
					<Breadcrumb.Link href={resolve('/dashboard', {})}>{mmT($mmLocale, "Home" )}</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item>
					<Breadcrumb.Page>{mmT($mmLocale, "Movies" )}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>
<main class="flex w-full flex-1 flex-col gap-4 p-4 pt-0">
	<h1 class="scroll-m-20 text-center text-4xl font-extrabold tracking-tight lg:text-5xl">{mmT($mmLocale, "Movies" )}</h1>
	<LibraryScan kind="movies" />
	{#await data.movies}
		<LoadingBar />
	{:then movies}
		<MediaLibrary items={movies} isTv={false}/>
	{/await}
	{#if importableMovies().length > 0}
		<details open={!!match} class="rounded-xl border bg-card p-4"><summary class="cursor-pointer font-medium">{mmT($mmLocale,'Directories needing review')} ({importableMovies().length})</summary>
		<div
			class="grid w-full auto-rows-min gap-4 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
		>
			{#each importableMovies().filter(x=>!match||x.directory===match).slice(0,limit) as importable (importable.directory)}
				<DetectedMediaCard isTv={false} directory={importable.directory}>
					<ImportCandidatesDialog
						isTv={false}
						name={importable.directory}
						candidates={importable.candidates}
					>
						{mmT($mmLocale, "Import movie" )}
					</ImportCandidatesDialog>
				</DetectedMediaCard>
			{/each}
		</div>
    {#if importableMovies().filter(x=>!match||x.directory===match).length>limit}<button type="button" class="rounded-lg border px-4 py-2" onclick={()=>limit+=40}>{mmT($mmLocale,'Show more entries')}</button>{/if}
		</details>
	{/if}
</main>
