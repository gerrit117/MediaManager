<script lang="ts">
    import { onMount } from 'svelte';
    import { invalidateAll } from '$app/navigation';
    import { Button } from '$lib/components/ui/button';
    import { locale, t } from '$lib/i18n';

    type Episode = { season: number; episode: number };
    type SearchStatus = {
        status: 'idle' | 'running' | 'completed' | 'failed' | 'interrupted';
        season_number?: number | null;
        episode_number?: number | null;
        current_season?: number | null;
        queued_downloads?: number;
        queued_episodes?: number;
        not_found?: Episode[];
        errors?: { season: number | null; message: string }[];
    };

    let { showId, seasonNumber, episodeNumber }: {
        showId: string;
        seasonNumber?: number;
        episodeNumber?: number;
    } = $props();
    let report = $state<SearchStatus>({ status: 'idle' });
    let starting = $state(false);
    let error = $state('');
    const endpoint = $derived(`/api/v1/tv/shows/${showId}/backfill`);
    const relevant = $derived(report.status !== 'idle' &&
        (seasonNumber === undefined || report.season_number === seasonNumber) &&
        (episodeNumber === undefined || report.episode_number === episodeNumber));
    let poll: ReturnType<typeof setTimeout> | undefined;
    let active = false;

    async function refresh() {
        const previous = report.status;
        try {
            const response = await fetch(endpoint);
            if (!response.ok) return;
            const next: SearchStatus = await response.json();
            if (!active) return;
            report = next;
            if (previous === 'running' && next.status !== 'running' && relevant) {
                await invalidateAll();
            }
        } finally {
            if (active && (report.status === 'running' || seasonNumber === undefined)) {
                poll = setTimeout(check, report.status === 'running' ? 2000 : 5000);
            }
        }
    }

    function check() {
        void refresh().catch(() => {});
    }

    async function start() {
        starting = true;
        error = '';
        if (poll) clearTimeout(poll);
        try {
            const query = new URLSearchParams();
            if (seasonNumber !== undefined) query.set('season_number', String(seasonNumber));
            if (episodeNumber !== undefined) query.set('episode_number', String(episodeNumber));
            const response = await fetch(query.size ? `${endpoint}?${query}` : endpoint, { method: 'POST' });
            if (!response.ok) {
                const payload = await response.json();
                throw Error(typeof payload.detail === 'string' ? payload.detail : 'Missing episode search failed. Check the server logs.');
            }
            report = { status: 'running', season_number: seasonNumber, episode_number: episodeNumber };
            await refresh();
        } catch (reason) {
            error = (reason as Error).message;
            if (!poll) check();
        } finally {
            starting = false;
        }
    }

    onMount(() => {
        active = true;
        if (episodeNumber === undefined) check();
        return () => {
            active = false;
            if (poll) clearTimeout(poll);
        };
    });
</script>

<div class="min-w-0 space-y-2">
    <Button class="h-auto min-h-10 whitespace-normal" variant="outline" disabled={starting || report.status === 'running'} onclick={start}>
        {t($locale, episodeNumber === undefined ? 'Find and download missing episodes' : 'Automatic search')}
    </Button>
    {#if relevant}
        <div class="space-y-1 text-sm text-muted-foreground" aria-live="polite">
            {#if report.status === 'running'}
                <p>{t($locale, 'Searching indexers…')}{report.current_season ? ` · ${t($locale, 'Season')} ${report.current_season}` : ''}</p>
            {:else if report.status === 'interrupted'}
                <p>{t($locale, 'Search interrupted. Start it again to check the remaining episodes.')}</p>
            {/if}
            {#if report.queued_episodes}
                <p>{t($locale, 'Episodes queued')}: {report.queued_episodes} · {t($locale, 'Downloads')}: {report.queued_downloads}</p>
            {:else if report.status === 'completed' && !report.not_found?.length && !report.errors?.length}
                <p>{t($locale, 'No missing aired episodes to queue.')}</p>
            {/if}
            {#if report.not_found?.length}
                <details>
                    <summary class="cursor-pointer">{t($locale, 'Episodes without a suitable release')}: {report.not_found.length}</summary>
                    <p class="mt-1 break-words">{report.not_found.map(({ season, episode }) => `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')}`).join(', ')}</p>
                </details>
            {/if}
            {#each report.errors ?? [] as failure}
                <p class="text-destructive" role="alert">{failure.season ? `${t($locale, 'Season')} ${failure.season} · ` : ''}{t($locale, failure.message)}</p>
            {/each}
        </div>
    {/if}
    {#if error}<p class="text-sm text-destructive" role="alert">{t($locale, error)}</p>{/if}
</div>
