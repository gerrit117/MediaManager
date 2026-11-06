<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import {
		convertTorrentSeasonRangeToIntegerRange,
		getTorrentQualityString,
		getTorrentStatusString
	} from '$lib/utils.js';
	import type { components } from '$lib/api/api';
	import { getContext, onMount } from 'svelte';
	import { loadDownloadProgress, type DownloadProgress } from '$lib/download-progress';
	import { Button } from '$lib/components/ui/button';
	import client from '$lib/api';
	import { toast } from 'svelte-sonner';
	import DeleteTorrentDialog from '$lib/components/torrents/delete-torrent-dialog.svelte';
	import EditTorrentDialog from '$lib/components/torrents/edit-torrent-dialog.svelte';
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	let {
		torrents,
		isShow = true,
		showId,
		movieId
	}: {
		torrents:
			| components['schemas']['MovieTorrent'][]
			| components['schemas']['RichSeasonTorrent'][];
		isShow: boolean;
		showId?: string;
		movieId?: string;
	} = $props();

	let progress = $state<Record<string, DownloadProgress>>({});
	onMount(() => {
		let active = true;
		const refresh = async () => {
			if (!torrents.length || document.visibilityState !== 'visible') return;
			const result = await loadDownloadProgress();
			if (active) progress = result;
		};
		void refresh();
		const interval = setInterval(refresh, 5000);
		return () => { active = false; clearInterval(interval); };
	});
	function statusLabel(state: string | undefined, fallback: components['schemas']['TorrentStatus']) {
		const names: Record<string, string> = { Downloading: 'Lädt herunter', Queued: 'Warteschlange', Paused: 'Pausiert', QueuePaused: 'Warteschlange pausiert', Completed: 'Abgeschlossen', Failed: 'Fehlgeschlagen', Extracting: 'Entpackt', Moving: 'Verschiebt', Running: 'Nachbearbeitung', Repairing: 'Repariert', Verifying: 'Prüft', QuickCheck: 'Prüft', Fetching: 'Lädt Reparaturdaten', Propagating: 'Wartet auf Verfügbarkeit', Unknown: 'Status unbekannt' };
		return state ? (names[state] ?? state) : getTorrentStatusString(fallback);
	}
	let user: () => components['schemas']['UserRead'] = getContext('user');

	async function retryTorrentDownload(
		torrent: components['schemas']['MovieTorrent'] | components['schemas']['RichSeasonTorrent']
	) {
		console.log(`Retrying download for torrent ${torrent.torrent_title}`);
		const { error } = await client.POST('/api/v1/torrent/{torrent_id}/retry', {
			params: {
				path: {
					torrent_id: torrent.torrent_id!
				}
			}
		});
		if (error) {
			toast.error(mmT($mmLocale,(error as { detail?: string })?.detail ?? 'Downloadmanager-Anfrage fehlgeschlagen.'));
		} else {
			console.log(`Successfully retried download for torrent ${torrent.torrent_title}`);
			toast.success(mmT($mmLocale,'Downloadmanager-Anfrage gesendet.'));
		}
		await invalidateAll();
	}
</script>

<div class="grid min-w-0 gap-4" aria-label={mmT($mmLocale, "Downloads")}>
	{#each torrents as torrent (torrent.torrent_id)}
		{@const live = progress[torrent.torrent_id]}
		{@const percent = live?.percent ?? (torrent.imported ? 100 : null)}
		{@const quality = getTorrentQualityString(torrent.quality)}
		<article class="min-w-0 overflow-hidden rounded-xl border bg-card" data-download-card>
			<div class="min-w-0 space-y-4 p-4 sm:p-5">
				<div class="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
					<div class="min-w-0 flex-1">
						{#if isShow && showId}
							<a href={resolve('/dashboard/tv/[showId]', { showId })} class="block break-words font-semibold leading-relaxed hover:text-primary [overflow-wrap:anywhere]">{torrent.torrent_title}</a>
						{:else if !isShow && movieId}
							<a href={resolve('/dashboard/movies/[movieId]', { movieId })} class="block break-words font-semibold leading-relaxed hover:text-primary [overflow-wrap:anywhere]">{torrent.torrent_title}</a>
						{:else}
							<p class="break-words font-semibold leading-relaxed [overflow-wrap:anywhere]">{torrent.torrent_title}</p>
						{/if}
					</div>
					<span class="w-fit max-w-full rounded-full bg-muted px-3 py-1 text-sm font-medium sm:shrink-0">{mmT($mmLocale,statusLabel(live?.state, torrent.status))}</span>
				</div>
				<div class="flex flex-wrap items-center gap-2 text-xs">
					<span class="rounded-md border px-2 py-1">{torrent.usenet ? 'Usenet / NZB' : 'Torrent'}</span>
					{#if quality !== 'unknown'}<span class="rounded-md border px-2 py-1">{quality}</span>{/if}
					{#if isShow}<span class="rounded-md border px-2 py-1">{mmT($mmLocale, "Staffel" )} {convertTorrentSeasonRangeToIntegerRange((torrent as components['schemas']['RichSeasonTorrent']).seasons!)}</span>{/if}
					<span class={torrent.imported ? 'text-emerald-500' : 'text-muted-foreground'}>{torrent.imported ? 'In der Bibliothek' : 'Import steht aus'}</span>
				</div>
				<div class="space-y-2">
					<div class="flex items-center justify-between gap-3 text-sm">
						<span class="text-muted-foreground">{mmT($mmLocale, "Fortschritt" )}</span>
						<span class="font-medium tabular-nums">{percent !== null && Number.isFinite(percent) ? percent.toLocaleString('de-DE', { maximumFractionDigits: 1 }) + ' %' : mmT($mmLocale, "Nicht verfügbar")}</span>
					</div>
					{#if percent !== null && Number.isFinite(percent)}
						<div class="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={mmT($mmLocale, "Downloadfortschritt")} aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}>
							<div class="h-full rounded-full bg-primary transition-[width] duration-500" style:width={`${Math.max(0, Math.min(100, percent))}%`}></div>
						</div>
					{/if}
				</div>
				{#if torrent.file_path_suffix}<p class="break-words text-xs text-muted-foreground">{mmT($mmLocale, "Dateizusatz:" )} {torrent.file_path_suffix}</p>{/if}
			</div>
			{#if user().is_superuser}
				<footer class="flex flex-wrap items-center justify-end gap-2 border-t bg-muted/20 px-4 py-3 sm:px-5" aria-label={mmT($mmLocale, "Download-Aktionen")}>
					{#if live?.state === 'Paused' || live?.state === 'Failed'}
						<Button variant="secondary" onclick={() => retryTorrentDownload(torrent)}>{live?.state === 'Paused' ? mmT($mmLocale, "Fortsetzen") : mmT($mmLocale, "Erneut versuchen")}</Button>
					{/if}
					<EditTorrentDialog {torrent} />
					<DeleteTorrentDialog usenet={torrent.usenet} torrentName={torrent.torrent_title} torrentId={torrent.torrent_id!} />
				</footer>
			{/if}
		</article>
	{/each}
</div>
