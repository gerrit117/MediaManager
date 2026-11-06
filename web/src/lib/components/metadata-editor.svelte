<script lang="ts">
 import {getContext} from 'svelte';
 import {invalidateAll} from '$app/navigation';
 import {locale,t} from '$lib/i18n';
 import {ExternalLink,Pencil,Database,Search,LoaderCircle} from 'lucide-svelte';
 let {media,isTv=false}:{media:any;isTv?:boolean}=$props();
 const user=getContext<()=>{is_superuser:boolean}>('user');
 let open=$state(false),busy=$state(false),error=$state(''),message=$state(''),name=$state(''),year=$state(''),overview=$state(''),provider=$state('tvdb'),external=$state(''),query=$state(''),results=$state<any[]>([]),refresh=$state(false);
 const endpoint='/api/v1/library/metadata/';
 let kind=$derived(isTv?'tv':'movies');
 let link=$derived(media.metadata_provider==='tmdb'?'https://www.themoviedb.org/'+(isTv?'tv/':'movie/')+media.external_id:'https://thetvdb.com/dereferrer/'+(isTv?'series/':'movie/')+media.external_id);
 function edit(){name=media.name;year=String(media.year??'');overview=media.overview??'';provider=media.metadata_provider;external=String(media.external_id);query=media.name;results=[];refresh=false;error='';message='';open=!open;}
 async function json(r:Response){const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?t($locale,data.detail):t($locale,'Details could not be saved.'));return data;}
 async function search(e:SubmitEvent){e.preventDefault();if(busy)return;busy=true;error='';try{const r=await fetch('/api/v1/'+(isTv?'tv':'movies')+'/search?metadata_provider='+provider+'&query='+encodeURIComponent(query));results=await json(r);}catch(e){error=(e as Error).message;}finally{busy=false;}}
 async function preview(id=external){if(busy)return;external=String(id);busy=true;error='';try{const data=await json(await fetch(endpoint+kind+'/'+media.id+'/preview?provider='+provider+'&external_id='+encodeURIComponent(external)));name=data.name;year=String(data.year??'');overview=data.overview??'';refresh=true;message=t($locale,'Metadata loaded. Review the details and save.');}catch(e){error=(e as Error).message;}finally{busy=false;}}
 async function save(e:SubmitEvent){e.preventDefault();if(busy)return;const changed=provider!==media.metadata_provider||Number(external)!==media.external_id;if(changed&&!confirm(t($locale,'Change the metadata assignment? Files stay in place; existing seasons and episodes remain linked by number. Check episode ordering after saving.')))return;busy=true;error='';message='';try{const data=await json(await fetch(endpoint+kind+'/'+media.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,external_id:Number(external),previous_provider:media.metadata_provider,previous_external_id:media.external_id,name,year:year?Number(year):null,overview,refresh_metadata:refresh,confirm_identity_change:changed})}));await invalidateAll();message=t($locale,data.warning??'Details saved.');if(!data.warning)open=false;dispatchEvent(new Event('mediamanager-poster-updated'));}catch(e){error=(e as Error).message;}finally{busy=false;}}
</script>
<section class="space-y-4 rounded-xl border bg-card p-5" aria-label={t($locale,'Metadata assignment')}>
 <div class="flex flex-wrap items-center justify-between gap-3">
  <div><h2 class="flex items-center gap-2 font-semibold"><Database class="size-4 text-primary"/>{t($locale,'Metadata assignment')}</h2><a href={link} target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary">{media.metadata_provider.toUpperCase()} · {media.external_id}<ExternalLink class="size-3"/></a></div>
  {#if user()?.is_superuser}<button type="button" class="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm" onclick={edit} disabled={busy}><Pencil class="size-4"/>{t($locale,open?'Cancel':'Edit details')}</button>{/if}
 </div>
 {#if open&&user()?.is_superuser}
  <div class="grid min-w-0 gap-4 lg:grid-cols-2">
   <div class="space-y-4 rounded-xl border p-4">
    <h3 class="font-medium">{t($locale,'Find the correct title')}</h3>
    <form onsubmit={search} class="space-y-3">
     <label class="block space-y-2 text-sm"><span>{t($locale,'Metadata provider')}</span><select class="w-full rounded-lg border bg-background p-2.5" bind:value={provider} onchange={()=>{refresh=false;results=[];}} disabled={busy}><option value="tmdb">TMDB</option><option value="tvdb">TVDB</option></select></label>
     <label class="block space-y-2 text-sm"><span>{t($locale,'Search title')}</span><input class="w-full min-w-0 rounded-lg border bg-background p-2.5" bind:value={query} required disabled={busy}/></label>
     <button class="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm" disabled={busy}><Search class="size-4"/>{t($locale,'Search')}</button>
    </form>
    {#if results.length}<div class="max-h-80 space-y-2 overflow-y-auto">{#each results as result (result.external_id)}<button type="button" class="flex w-full items-center gap-3 rounded-lg border p-2 text-left hover:bg-muted" disabled={busy} onclick={()=>preview(result.external_id)}>{#if result.poster_path}<img src={result.poster_path} alt="" class="h-16 w-11 shrink-0 rounded object-cover" loading="lazy"/>{/if}<span class="min-w-0"><strong class="block truncate text-sm">{result.name}</strong><span class="text-xs text-muted-foreground">{result.year??'—'} · {provider.toUpperCase()} {result.external_id}</span></span></button>{/each}</div>{/if}
    <p class="text-xs leading-relaxed text-muted-foreground">{t($locale,'Only change the provider ID when correcting an assignment. Files, requests and monitoring settings are preserved.')}</p>
   </div>
   <form onsubmit={save} class="space-y-4 rounded-xl border p-4">
    <label class="block space-y-2 text-sm"><span>TMDB / TVDB ID</span><div class="flex min-w-0 gap-2"><input type="number" min="1" step="1" required class="w-full min-w-0 rounded-lg border bg-background p-2.5" bind:value={external} oninput={()=>refresh=false} disabled={busy}/><button type="button" class="shrink-0 rounded-lg border px-3 text-xs" onclick={()=>preview()} disabled={busy||!external}>{t($locale,'Load metadata')}</button></div></label>
    <label class="block space-y-2 text-sm"><span>{t($locale,'Title')}</span><input required maxlength="300" class="w-full rounded-lg border bg-background p-2.5" bind:value={name} disabled={busy}/></label>
    <label class="block space-y-2 text-sm"><span>{t($locale,'Year')}</span><input type="number" min="1800" max="2200" class="w-full rounded-lg border bg-background p-2.5" bind:value={year} disabled={busy}/></label>
    <label class="block space-y-2 text-sm"><span>{t($locale,'Overview')}</span><textarea rows="5" maxlength="50000" class="w-full rounded-lg border bg-background p-2.5" bind:value={overview} disabled={busy}></textarea></label>
    <button disabled={busy} class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">{#if busy}<LoaderCircle class="size-4 animate-spin"/>{/if}{t($locale,'Save details')}</button>
   </form>
  </div>
 {/if}
 {#if error}<p role="alert" class="text-sm text-destructive">{error}</p>{/if}
 {#if message}<p role="status" class="text-sm text-muted-foreground">{message}</p>{/if}
</section>
