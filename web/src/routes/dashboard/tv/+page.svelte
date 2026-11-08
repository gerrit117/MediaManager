<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import { getFullyQualifiedMediaName } from '$lib/utils';
	import MediaLibrary from '$lib/components/media-library.svelte';
	import { resolve } from '$app/paths';
	import ImportCandidatesDialog from '$lib/components/import-media/import-candidates-dialog.svelte';
	import DetectedMediaCard from '$lib/components/import-media/detected-media-card.svelte';
	import type { components } from '$lib/api/api';
	import { getContext,onMount } from 'svelte';
	import type { PageProps } from './$types';
	import LoadingBar from '$lib/components/loading-bar.svelte';
	import LibraryScan from '$lib/components/import-media/library-scan.svelte';

	let { data }: PageProps = $props();
    let match=$state('');let limit=$state(40);
    const scanner=getContext<{run:(kind:'movies'|'tv')=>Promise<void>}>('libraryScan');
    onMount(()=>{match=new URLSearchParams(location.search).get('match')??'';if(match)void scanner.run('tv');});

	let importableShows: () => components['schemas']['MediaImportSuggestion'][] =
		getContext('importableShows');
</script>

<svelte:head>
	<title>{mmT($mmLocale, "TV Shows - MediaManager" )}</title>
	<meta content="Browse and manage your TV show collection in MediaManager" name="description" />
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
					<Breadcrumb.Page>{mmT($mmLocale, "Shows" )}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>
<main class="flex w-full flex-col gap-4 p-4 pt-0">
	<h1 class="scroll-m-20 text-center text-4xl font-extrabold tracking-tight lg:text-5xl">
		{mmT($mmLocale, "TV Shows" )}
	</h1>
	<LibraryScan kind="tv" />
	{#await data.tvShows}
		<LoadingBar />
	{:then tvShows}
		<MediaLibrary items={tvShows??[]} isTv={true}/>
	{/await}
	{#if importableShows().length > 0}
		<details open={!!match} class="rounded-xl border bg-card p-4"><summary class="cursor-pointer font-medium">{mmT($mmLocale,'Directories needing review')} ({importableShows().length})</summary>
		<div
			class="grid w-full auto-rows-min gap-4 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
		>
			{#each importableShows().filter(x=>!match||x.directory===match).slice(0,limit) as importable (importable.directory)}
				<DetectedMediaCard isTv={true} directory={importable.directory}>
					<ImportCandidatesDialog
						isTv={true}
						name={importable.directory}
						candidates={importable.candidates}
					>
						{mmT($mmLocale, "Import TV show" )}
					</ImportCandidatesDialog>
				</DetectedMediaCard>
			{/each}
		</div>
    {#if importableShows().filter(x=>!match||x.directory===match).length>limit}<button type="button" class="rounded-lg border px-4 py-2" onclick={()=>limit+=40}>{mmT($mmLocale,'Show more entries')}</button>{/if}
		</details>
	{/if}
</main>
