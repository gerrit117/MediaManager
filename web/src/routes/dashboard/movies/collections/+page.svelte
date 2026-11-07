<script lang="ts">
 import {onMount,getContext} from 'svelte';
 import {locale,t} from '$lib/i18n';
 import {goto} from '$app/navigation';
 import {base} from '$app/paths';
 import type {components} from '$lib/api/api';
 let user:()=>components['schemas']['UserRead']=getContext('user');
 let collections=$state<any[]>([]),progress=$state<any>(null),message=$state(''),busy=$state(false);let filter=$state('');
 let selected=$state<number|null>(null);
 async function load(){try{const r=await fetch('/api/v1/library/collections');if(!r.ok)throw Error(t($locale,'Collections could not be loaded.'));collections=await r.json();}catch(e){message=(e as Error).message;}}
 onMount(()=>{load();const timer=setInterval(async()=>{try{const r=await fetch('/api/v1/library/collections/refresh-status');if(r.ok){const previous=progress?.running;progress=await r.json();if(previous&&!progress.running)await load();}}catch{}},2500);return()=>clearInterval(timer);});
 async function refresh(){message='';try{const r=await fetch('/api/v1/library/collections/refresh',{method:'POST'});const data=await r.json();if(!r.ok)throw Error(data.detail);progress=data;}catch(e){message=(e as Error).message;}}
 async function openMovie(part:any){busy=true;message='';try{let id=part.movie_id;if(!id){const r=await fetch('/api/v1/movies?'+new URLSearchParams({movie_id:String(part.tmdb_id),metadata_provider:'tmdb',language:$locale}),{method:'POST'});const data=await r.json();if(!r.ok)throw Error(data.detail??t($locale,'Movie could not be added.'));id=data.id;}await goto(base+'/dashboard/movies/'+id);}catch(e){message=(e as Error).message;}finally{busy=false;}}
</script>
<svelte:head><title>{t($locale,'Movie collections')} – MediaManager</title></svelte:head>
<main class="mx-auto w-full min-w-0 max-w-7xl space-y-5 p-4">
 <nav class="flex gap-3"><a class="rounded-lg border px-4 py-2" href={base+'/dashboard/movies'}>{t($locale,'Movies')}</a><span class="rounded-lg bg-primary px-4 py-2 text-primary-foreground">{t($locale,'Movie collections')}</span></nav>
 <header class="flex flex-wrap items-center justify-between gap-3"><h1 class="text-3xl font-bold">{t($locale,'Movie collections')}</h1>{#if user().is_superuser}<button class="rounded-lg border px-4 py-2 disabled:opacity-50" disabled={progress?.running} onclick={refresh}>{t($locale,progress?.running?'Refreshing…':'Refresh collections')}</button>{/if}</header>
 <p class="text-sm text-muted-foreground">{t($locale,'Collection members are matched against your own library. Opening a missing movie lets you search or request it.')}</p>
 {#if progress?.running}<p role="status">{t($locale,'Refreshing…')} {progress.updated}</p>{/if}
 {#if message||progress?.error}<p role="alert" class="rounded-lg border border-destructive p-3 text-destructive">{t($locale,message||progress.error)}</p>{/if}
 <input class="w-full rounded-lg border bg-background p-3" aria-label={t($locale,'Search collections')} placeholder={t($locale,'Search collections')} bind:value={filter}/>
 {#if selected!==null}
  {@const collection=collections.find(c=>c.id===selected)}
  {#if collection}<section class="space-y-4 rounded-xl border p-4"><div class="flex justify-between gap-3"><h2 class="text-2xl font-semibold">{collection.name}</h2><button class="rounded-lg border px-3" onclick={()=>selected=null}>{t($locale,'Close')}</button></div><p class="text-sm text-muted-foreground">{collection.overview}</p><div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
   {#each collection.parts as part}<article class="flex min-w-0 flex-col overflow-hidden rounded-xl border"><div class="aspect-[2/3] bg-muted">{#if part.poster_url}<img src={part.poster_url} alt={part.name} class="h-full w-full object-cover" loading="lazy"/>{/if}</div><div class="flex flex-1 flex-col gap-2 p-3"><h3 class="text-sm font-semibold">{part.name}</h3><p class="text-xs text-muted-foreground">{part.year??'—'} · {t($locale,part.state==='available'?'Available':part.state==='upcoming'?'Upcoming':'Missing')}</p><button class="mt-auto rounded-lg border px-2 py-2 text-sm disabled:opacity-50" disabled={busy} onclick={()=>openMovie(part)}>{t($locale,part.available?'Open':user().is_superuser?'Search':'Request')}</button></div></article>{/each}
  </div></section>{/if}
 {/if}
 <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
 {#each collections.filter(c=>c.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase())) as collection}<button class="min-w-0 overflow-hidden rounded-xl border bg-card text-left transition hover:border-primary" onclick={()=>{selected=collection.id;window.scrollTo({top:0,behavior:'smooth'});}}><div class="aspect-[2/3] bg-muted">{#if collection.poster_url}<img src={collection.poster_url} alt={collection.name} class="h-full w-full object-cover" loading="lazy"/>{/if}</div><div class="space-y-1 p-3"><h2 class="break-words text-sm font-semibold">{collection.name}</h2><p class="text-xs text-muted-foreground">{collection.available_count} / {collection.parts.length} {t($locale,'Available')} · {collection.missing_count} {t($locale,'Missing')}</p></div></button>{:else}<p class="col-span-full text-muted-foreground">{t($locale,'No collections cached. An administrator can refresh them using TMDB or an existing Radarr metadata connection.')}</p>{/each}
 </div>
</main>
