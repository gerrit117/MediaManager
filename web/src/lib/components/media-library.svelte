<script lang="ts">
 import {locale,t} from '$lib/i18n';
 import {resolve} from '$app/paths';
 import {Search,LibraryBig,ArrowUpDown,Check,Radio} from 'lucide-svelte';
 import MediaPicture from '$lib/components/media-picture.svelte';
 let {items,isTv=false}:{items:any[];isTv?:boolean}=$props();
 let query=$state(''),sort=$state('title'),limit=$state(60);
 let results=$derived([...items].filter(x=>[x.name,x.year,x.external_id].join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a,b)=>sort==='newest'?(b.year??0)-(a.year??0)||a.name.localeCompare(b.name):sort==='oldest'?(a.year??0)-(b.year??0)||a.name.localeCompare(b.name):a.name.localeCompare(b.name,$locale)));
 $effect(()=>{query;sort;limit=60;});
</script>
<section class="space-y-5" aria-label={t($locale,'Media library')}>
 <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
  <p class="flex items-center gap-2 text-sm text-muted-foreground"><LibraryBig class="size-4"/>{results.length} {t($locale,isTv?'TV Shows':'Movies')}</p>
  <div class="flex min-w-0 flex-col gap-2 sm:flex-row">
   <label class="relative min-w-0 sm:w-72"><Search class="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground"/><input aria-label={t($locale,'Search library')} placeholder={t($locale,'Search library')} bind:value={query} class="h-10 w-full min-w-0 rounded-xl border bg-card pl-10 pr-3 text-sm"/></label>
   <label class="flex items-center gap-2 rounded-xl border bg-card px-3"><ArrowUpDown class="size-4 shrink-0 text-muted-foreground"/><select aria-label={t($locale,'Sort library')} bind:value={sort} class="h-10 min-w-0 flex-1 bg-transparent text-sm"><option value="title">{t($locale,'Title A–Z')}</option><option value="newest">{t($locale,'Newest first')}</option><option value="oldest">{t($locale,'Oldest first')}</option></select></label>
  </div>
 </div>
 <div class="grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
  {#each results.slice(0,limit) as media (media.id)}
   <a class="group min-w-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-primary" href={isTv?resolve('/dashboard/tv/[showId]',{showId:media.id}):resolve('/dashboard/movies/[movieId]',{movieId:media.id})} title={media.name}>
    <div class="relative overflow-hidden rounded-xl border border-white/10 shadow-md transition duration-200 group-hover:-translate-y-1 group-hover:shadow-xl">
     <MediaPicture {media}/>
     <div class="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/90 to-transparent px-3 pb-3 pt-12 text-xs text-white">
      <span class="rounded-md bg-black/60 px-2 py-1 font-medium">{media.metadata_provider?.toUpperCase()} · {media.external_id}</span>
      {#if media.continuous_download}<Radio class="size-4 text-emerald-300" aria-label={t($locale,'Monitored')}/>{:else if media.downloaded}<Check class="size-4 text-emerald-300" aria-label={t($locale,'Available')}/>{/if}
     </div>
    </div>
    <h2 class="mt-3 truncate text-sm font-semibold group-hover:text-primary">{media.name}</h2>
    <p class="mt-1 text-xs text-muted-foreground">{media.year??t($locale,'Year unknown')} · {t($locale,isTv?'TV Shows':'Movies')}</p>
   </a>
  {:else}<p class="col-span-full rounded-xl border border-dashed p-10 text-center text-muted-foreground">{t($locale,'No matching titles.')}</p>{/each}
 </div>
 {#if results.length>limit}<button type="button" class="mx-auto block rounded-xl border bg-card px-6 py-3 text-sm" onclick={()=>limit+=60}>{t($locale,'Show more entries')} ({Math.min(limit,results.length)} / {results.length})</button>{/if}
</section>
