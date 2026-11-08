<script lang="ts">
 import { getContext } from 'svelte';
 import * as Dialog from '$lib/components/ui/dialog';
 import { Button } from '$lib/components/ui/button';
 import RequestMediaDialog from '$lib/components/requests/request-media-dialog.svelte';
 import { locale, t } from '$lib/i18n';
 import { resolve } from '$app/paths';
 import type { components } from '$lib/api/api';
 let { open=$bindable(false), result, isShow, onAdd, adding=false, addError=null }: {
  open?:boolean; result:components['schemas']['MetaDataProviderSearchResult']; isShow:boolean;
  onAdd:()=>Promise<void>; adding?:boolean; addError?:string|null;
 }=$props();
 const user=getContext<()=>components['schemas']['UserRead']>('user');
 let metadata=$state<any>(null),error=$state(''),loading=$state(false);
 $effect(()=>{
  if(!open)return;
  const controller=new AbortController();
  metadata=null;error='';loading=true;
  fetch(`/api/v1/requests/preview/${isShow?'tv':'movie'}/${result.metadata_provider}/${result.external_id}?language=${$locale}`,{signal:controller.signal})
   .then(async response=>{const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not load title metadata. Please try again.');return data;})
   .then(data=>{if(!controller.signal.aborted)metadata=data;})
   .catch(reason=>{if(!controller.signal.aborted)error=reason.message;})
   .finally(()=>{if(!controller.signal.aborted)loading=false;});
  return()=>controller.abort();
 });
</script>
<Dialog.Root bind:open>
 <Dialog.Content class="max-h-[calc(100dvh-2rem)] w-[calc(100vw-1rem)] max-w-3xl overflow-y-auto overscroll-contain p-4 sm:p-6">
  <div class="grid min-w-0 grid-cols-[6rem_minmax(0,1fr)] items-start gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]">
   {#if result.poster_path}<img src={result.poster_path} alt={result.name} class="aspect-[2/3] w-full rounded-lg object-cover"/>{:else}<div class="flex aspect-[2/3] items-center justify-center rounded-lg bg-muted text-sm text-muted-foreground">{t($locale,'No poster available')}</div>{/if}
   <div class="min-w-0 space-y-3 pr-5">
    <Dialog.Title class="break-words text-xl leading-tight sm:text-2xl">{metadata?.name??result.name}</Dialog.Title>
    <Dialog.Description>{t($locale,isShow?'Series details':'Movie details')}</Dialog.Description>
    <div class="flex flex-wrap gap-2 text-sm">
     {#if metadata?.year??result.year}<span class="rounded-full bg-muted px-3 py-1">{metadata?.year??result.year}</span>{/if}
     {#if result.vote_average!=null}<span class="rounded-full bg-muted px-3 py-1">{t($locale,'Rating:')} {result.vote_average.toLocaleString($locale,{maximumFractionDigits:1})}/10</span>{/if}
    </div>
    {#if result.original_language}<p class="text-sm text-muted-foreground">{t($locale,'Original language')}: {result.original_language.toUpperCase()}</p>{/if}
    {#if isShow&&metadata?.seasons?.length}<p class="text-sm text-muted-foreground">{metadata.seasons.length} {t($locale,'Seasons')}</p>{/if}
   </div>
   <section class="col-span-full space-y-2"><h3 class="font-semibold">{t($locale,'Description')}</h3><p class="whitespace-pre-line text-sm leading-relaxed">{metadata?.overview||result.overview||t($locale,'No overview available')}</p></section>
   {#if loading}<p role="status" class="col-span-full text-sm text-muted-foreground">{t($locale,'Loading…')}</p>{/if}
   {#if error}<p role="alert" class="col-span-full text-sm text-destructive">{t($locale,error)}</p>{/if}
   <div class="col-span-full space-y-3 border-t pt-4">
    {#if addError}<p role="alert" class="text-sm text-destructive">{t($locale,addError)}</p>{/if}
    {#if result.added&&result.id}<Button class="min-h-11 w-full" href={resolve(isShow?'/dashboard/tv/[showId]':'/dashboard/movies/[movieId]',isShow?{showId:result.id}:{movieId:result.id})}>{t($locale,'Open in library')}</Button>
    {:else if !user?.()?.is_superuser}<RequestMediaDialog {result} {isShow}/>
    {:else}<Button class="min-h-11 w-full" disabled={adding} onclick={onAdd}>{t($locale,adding?'Loading…':isShow?'Add series':'Add movie')}</Button>{/if}
   </div>
  </div>
 </Dialog.Content>
</Dialog.Root>
