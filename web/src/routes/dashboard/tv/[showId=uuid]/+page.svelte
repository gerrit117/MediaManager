<script lang="ts">
 import ReleaseProtection from '$lib/components/release-protection.svelte';
    import {onMount} from 'svelte';
    import SeriesSeasons from '$lib/components/series-seasons.svelte';
    let monitorStatus = $state<any>(null);
    onMount(async()=>{try{const r=await fetch('/api/v1/tv/shows/'+show.id+'/monitor');if(r.ok)monitorStatus=await r.json();}catch{}});

	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import { goto } from '$app/navigation';
	import { ImageOff } from 'lucide-svelte';
	import * as Table from '$lib/components/ui/table/index.js';
	import { getContext } from 'svelte';
	import type { components } from '$lib/api/api';
	import { getFullyQualifiedMediaName } from '$lib/utils';
	import DownloadSeasonDialog from '$lib/components/download-dialogs/download-season-dialog.svelte';
	import CheckmarkX from '$lib/components/checkmark-x.svelte';
	import { page } from '$app/state';
	import TorrentTable from '$lib/components/torrents/torrent-table.svelte';
	import RequestSeasonDialog from '$lib/components/requests/request-season-dialog.svelte';
	import MediaPicture from '$lib/components/media-picture.svelte';
	import MetadataEditor from '$lib/components/metadata-editor.svelte';
	import { Switch } from '$lib/components/ui/switch/index.js';
	import { toast } from 'svelte-sonner';
	import { Label } from '$lib/components/ui/label';
	import LibraryCombobox from '$lib/components/library-combobox.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import DeleteMediaDialog from '$lib/components/delete-media-dialog.svelte';
	import { resolve } from '$app/paths';
	import client from '$lib/api';

	let show: components['schemas']['PublicShow'] = $derived(page.data.showData);
	let torrents: components['schemas']['RichShowTorrent'] = $derived(page.data.torrentsData);
	let user: () => components['schemas']['UserRead'] = getContext('user');

	let continuousDownloadEnabled = $derived(show.continuous_download);

	let monitorBusy=$state(false);
    async function toggle_continuous_download() {
        if(monitorBusy)return;
        monitorBusy=true;
        const desired=!continuousDownloadEnabled;
        try {
            const {response}=await client.POST('/api/v1/tv/shows/{show_id}/continuousDownload',{
                params:{path:{show_id:show.id},query:{continuous_download:desired}}
            });
            if(!response.ok)throw new Error();
            continuousDownloadEnabled=desired;
            try{const r=await fetch('/api/v1/tv/shows/'+show.id+'/monitor');if(r.ok)monitorStatus=await r.json();}catch{}
            toast.success(mmT($mmLocale,'Monitoring updated.'));
        }catch{toast.error(mmT($mmLocale,'Monitoring could not be updated.'));}
        finally{monitorBusy=false;}
    }

</script>

<svelte:head>
	<title>{getFullyQualifiedMediaName(show)} - MediaManager</title>
	<meta
		content="View details and manage downloads for {getFullyQualifiedMediaName(
			show
		)} in MediaManager"
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
					<Breadcrumb.Link href={resolve('/dashboard', {})}>{mmT($mmLocale, "Home" )}</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item>
					<Breadcrumb.Link href={resolve('/dashboard/tv', {})}>{mmT($mmLocale, "Shows" )}</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item>
					<Breadcrumb.Page>{getFullyQualifiedMediaName(show)}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>
<h1 class="px-4 text-center text-2xl font-bold tracking-tight sm:text-4xl">
	{getFullyQualifiedMediaName(show)}
</h1>
<main class="mx-auto flex w-full flex-1 flex-col gap-4 p-4 md:max-w-[80em]">
 <ReleaseProtection kind="show" mediaId={show.id!}/>

	<MetadataEditor media={show} isTv={true}/>
	<div class="flex flex-col gap-4 md:flex-row md:items-stretch">
		<div class="mx-auto w-40 shrink-0 overflow-hidden rounded-xl bg-muted/50 sm:w-52 md:mx-0 md:w-1/3 md:max-w-sm">
			{#if show.id}
				<MediaPicture media={show} />
			{:else}
				<div
					class="flex aspect-9/16 h-auto w-full items-center justify-center rounded-lg bg-gray-200 text-gray-500"
				>
					<ImageOff size={48} />
				</div>
			{/if}
		</div>
		<div class="w-full flex-auto rounded-xl md:w-1/4">
			<Card.Root class="w-full">
				<Card.Header>
					<Card.Title>{mmT($mmLocale, "Overview" )}</Card.Title>
				</Card.Header>
				<Card.Content>
					<p class="leading-7 not-first:mt-6">
						{show.overview}
					</p>
				</Card.Content>
			</Card.Root>
		</div>
		<div
			class="flex w-full flex-auto flex-col items-center justify-start gap-4 rounded-xl md:w-1/3 md:max-w-[40em]"
		>
			{#if user().is_superuser}
				<Card.Root class="w-full">
					<Card.Header>
						<Card.Title>{mmT($mmLocale, "Administrator Controls" )}</Card.Title>
					</Card.Header>
					<Card.Content class="flex flex-col items-center gap-4">
						{#if !show.ended}
							<div class="flex items-center gap-3">
								<Switch
                                    disabled={monitorBusy}
									bind:checked={() => continuousDownloadEnabled, toggle_continuous_download}
									id="continuous-download-checkbox"
								/>
								<Label for="continuous-download-checkbox">
									{mmT($mmLocale, "Monitor new episodes and seasons" )}
                                    {#if monitorStatus?.since}<span class="block text-xs">{mmT($mmLocale,'Monitoring since')}: {monitorStatus.since}</span>{/if}
                                    {#if monitorStatus?.uncertain}<span role="alert" class="block text-xs text-destructive">{mmT($mmLocale,'A submission could not be confirmed. Check the downloader before retrying; automatic resubmission is blocked.')}</span>{/if}
                                    {#if monitorStatus?.missing_dates}<span class="block text-xs text-muted-foreground">{mmT($mmLocale,'Episodes without an air date are skipped until metadata is available.')}</span>{/if}

                                    <span class="block text-xs text-muted-foreground">{mmT($mmLocale,"Searches every 30 minutes for aired episodes from activation onward, including weekly releases. Existing files and active downloads are skipped; improved language/resolution can be upgraded.")}</span>
								</Label>
							</div>
						{/if}
						<LibraryCombobox media={show} mediaType="tv" />
						<DeleteMediaDialog isShow={true} media={show} />
					</Card.Content>
				</Card.Root>
			{/if}
			<Card.Root class="w-full">
				<Card.Header>
					<Card.Title>{mmT($mmLocale, "Download Options" )}</Card.Title>
				</Card.Header>
				<Card.Content class="flex flex-col items-center gap-4">
					{#if user().is_superuser}
						<DownloadSeasonDialog {show} />
					{:else}
						<RequestSeasonDialog {show} />
					{/if}
				</Card.Content>
			</Card.Root>
		</div>
	</div>
	<div class="flex-1 rounded-xl">
		<Card.Root class="w-full">
			<Card.Header>
				<Card.Title>{mmT($mmLocale, "Season Details" )}</Card.Title>
				<Card.Description>
					{mmT($mmLocale, "A list of all seasons for" )} {getFullyQualifiedMediaName(show)}.
				</Card.Description>
			</Card.Header>
			<Card.Content class="w-full overflow-x-auto">
				<SeriesSeasons {show}/>
			</Card.Content>
		</Card.Root>
	</div>
	<div class="flex-1 rounded-xl">
		<Card.Root>
			<Card.Header>
				<Card.Title>{mmT($mmLocale, "Download-Informationen" )}</Card.Title>
				<Card.Description>{mmT($mmLocale, "Alle Downloads dieser Serie." )}</Card.Description>
			</Card.Header>

			<Card.Content class="w-full overflow-x-auto">
				<TorrentTable isShow={true} torrents={torrents.torrents} showId={show.id} />
			</Card.Content>
		</Card.Root>
	</div>
</main>
