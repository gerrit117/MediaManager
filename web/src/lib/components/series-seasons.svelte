<script lang="ts">
 import ReleaseProtection from '$lib/components/release-protection.svelte';
 import {locale,t} from '$lib/i18n';
 import {getContext} from 'svelte';
 import DownloadSeasonDialog from '$lib/components/download-dialogs/download-season-dialog.svelte';
 import RequestSeasonDialog from '$lib/components/requests/request-season-dialog.svelte';
 import MissingEpisodesSearch from '$lib/components/missing-episodes-search.svelte';
 import EpisodeAction from '$lib/components/episode-action.svelte';
 import type {components} from '$lib/api/api';
 let {show,onlySeason}:{show:components['schemas']['PublicShow'];onlySeason?:string}=$props();
 let user:()=>components['schemas']['UserRead']=getContext('user');
 let expandedSeasonIds = $state<Record<string, boolean>>({});
 let seasons=$derived((show.seasons as any[]).filter(s=>s.episodes.length>0&&(!onlySeason||s.id===onlySeason)).sort((a,b)=>(a.number===0?9999:a.number)-(b.number===0?9999:b.number)));
 const states:Record<string,string>={available:'Available',complete:'Complete',missing:'Missing',upcoming:'Upcoming',unknown:'Air date unknown',downloading:'Downloading',attention:'Check download'};
</script>
<div class="space-y-3">
 {#each seasons as season (season.id)}
 <details class="overflow-hidden rounded-xl border" open={!!onlySeason} ontoggle={(event) => { expandedSeasonIds[season.id] = event.currentTarget.open; }}>
  <summary class="cursor-pointer space-y-1 bg-muted/30 p-4"><span class="font-semibold">{season.number===0?t($locale,'Specials'):t($locale,'Season')+' '+season.number}</span><span class="ml-3 text-sm text-muted-foreground">{season.available_count??0} / {season.episodes.length} {t($locale,'Available')}</span>{#if season.number!==0&&season.missing_count>0}<span class="ml-2 text-sm text-amber-600">{season.missing_count} {t($locale,'Missing')}</span>{/if}{#if season.upcoming_count>0}<span class="ml-2 text-sm text-muted-foreground">{season.upcoming_count} {t($locale,'Upcoming')}</span>{/if}</summary>
  <div class="space-y-3 p-3">
 <ReleaseProtection kind="season" mediaId={season.id}/>
   <div class="flex flex-wrap items-center justify-between gap-2"><p class="text-sm text-muted-foreground">{season.name}</p>{#if !season.downloaded}{#if user().is_superuser}<DownloadSeasonDialog {show} seasonNumber={season.number} triggerText="Interactive search"/>{:else}<RequestSeasonDialog {show} seasonId={season.id} triggerText="Request season"/>{/if}{/if}</div>
   {#if user().is_superuser && season.number > 0 && (onlySeason || expandedSeasonIds[season.id])}
    <MissingEpisodesSearch showId={show.id} seasonNumber={season.number}/>
   {/if}
   {#each season.episodes as episode (episode.id)}
   <article class="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
    <div class="min-w-0 flex-1"><div class="flex flex-wrap items-center gap-2"><span class="text-xs text-muted-foreground">S{String(season.number).padStart(2,'0')}E{String(episode.number).padStart(2,'0')}</span><h4 class="break-words text-sm font-medium">{episode.title}</h4></div><p class="mt-1 text-xs text-muted-foreground">{episode.air_date??'—'} · {t($locale,states[episode.state]??'Air date unknown')}{episode.requested?' · '+t($locale,'Requested'):''}</p></div>
    {#if user().is_superuser && season.number > 0 && episode.state === 'missing' && (onlySeason || expandedSeasonIds[season.id])}
     <MissingEpisodesSearch showId={show.id} seasonNumber={season.number} episodeNumber={episode.number}/>
    {/if}
    <ReleaseProtection kind="episode" mediaId={episode.id}/>{#if (user().is_superuser||!episode.downloaded)&&episode.state!=='downloading'&&episode.state!=='attention'}<EpisodeAction {episode} showName={show.name} seasonNumber={season.number}/>{/if}
   </article>
   {/each}
  </div>
 </details>
 {:else}<p class="text-sm text-muted-foreground">{t($locale,'No season data available.')}</p>{/each}
</div>
