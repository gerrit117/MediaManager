<script lang="ts">
 import {locale,t} from '$lib/i18n';
 import {getContext} from 'svelte';
 import * as Dialog from '$lib/components/ui/dialog';
 import {buttonVariants} from '$lib/components/ui/button';
 import {toast} from 'svelte-sonner';
 import {invalidateAll} from '$app/navigation';
 import RequestQuota from '$lib/components/request-quota.svelte';
 import type {components} from '$lib/api/api';
 let {episode,showName,seasonNumber}:{episode:any;showName:string;seasonNumber:number}=$props();
 let user:()=>components['schemas']['UserRead']=getContext('user');
 let overrideLock=$state(false);let open=$state(false),busy=$state(false),message=$state('');let releases=$state<any[]|null>(null);let min=$state(3),wanted=$state(2);
 const qualities=[{value:1,label:'2160p'},{value:2,label:'1080p'},{value:3,label:'720p'},{value:4,label:'480p'}];
 async function api(path:string,method='GET',body?:any){const r=await fetch('/api/v1/tv/episodes/'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:t($locale,'Request failed'));return data;}
 async function search(){busy=true;message='';releases=null;try{releases=await api(episode.id+'/releases');}catch(e){message=(e as Error).message;}finally{busy=false;}}
 async function download(id:string){busy=true;message='';try{if(episode.downloaded&&!confirm(t($locale,'Replace the selected existing files after successful import? Originals will be archived.')))return;await api(episode.id+'/download?'+new URLSearchParams({result_id:id,replace_existing:'true',override_lock:String(overrideLock)}),'POST');toast.success(t($locale,'Download submitted'));open=false;await invalidateAll();}catch(e){message=(e as Error).message;}finally{busy=false;}}
 async function request(){busy=true;message='';try{await api('requests','POST',{episode_id:episode.id,min_quality:Number(min),wanted_quality:Number(wanted)});toast.success(t($locale,'Request submitted'));open=false;await invalidateAll();}catch(e){message=(e as Error).message;}finally{busy=false;}}
</script>
<Dialog.Root bind:open>
 <Dialog.Trigger class={buttonVariants({variant:'outline',size:'sm'})} onclick={()=>{message='';releases=null;}} disabled={episode.requested&&!user().is_superuser}>{t($locale,episode.requested&&!user().is_superuser?'Requested':user().is_superuser?'Interactive search':'Request')}</Dialog.Trigger>
 <Dialog.Content class="max-h-[90vh] w-[calc(100vw-2rem)] max-w-4xl overflow-y-auto">
  <Dialog.Header><Dialog.Title>{showName} · S{String(seasonNumber).padStart(2,'0')}E{String(episode.number).padStart(2,'0')}</Dialog.Title><Dialog.Description>{episode.title} · {t($locale,'Release rules and monthly request policies apply.')}</Dialog.Description></Dialog.Header>
  {#if user().is_superuser}
   <label class="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" bind:checked={overrideLock}/>{t($locale,'Explicitly override release protection for this manual download')}</label>
   <button class="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" disabled={busy} onclick={search}>{t($locale,busy?'Searching…':'Search releases')}</button>
   {#if releases}<p>{releases.length} {t($locale,'Releases')}</p>{#each releases as release}<article class="min-w-0 space-y-2 rounded-xl border p-3"><h3 class="break-words text-sm font-medium">{release.title}</h3><div class="flex flex-wrap items-center justify-between gap-2 text-sm"><span>{release.usenet?'Usenet / NZB':'Torrent'} · {release.indexer??''}</span><button class="rounded-lg border px-3 py-2 disabled:opacity-50" disabled={busy||release.rejected} onclick={()=>download(release.id)}>{t($locale,'Download')}</button></div></article>{:else}<p>{t($locale,'No matching releases found.')}</p>{/each}{/if}
  {:else}
   <RequestQuota/>
   <label>{t($locale,'Minimum quality')}<select class="ml-2 rounded border bg-background p-2" bind:value={min}>{#each qualities as q}<option value={q.value}>{q.label}</option>{/each}</select></label>
   <label>{t($locale,'Wanted quality')}<select class="ml-2 rounded border bg-background p-2" bind:value={wanted}>{#each qualities as q}<option value={q.value}>{q.label}</option>{/each}</select></label>
   <button class="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" disabled={busy||Number(wanted)>Number(min)} onclick={request}>{t($locale,'Request episode')}</button>
  {/if}
  {#if message}<p role="alert" class="text-destructive">{t($locale,message)}</p>{/if}
 </Dialog.Content>
</Dialog.Root>
