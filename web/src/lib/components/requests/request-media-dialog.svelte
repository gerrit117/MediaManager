<script lang="ts">
 import * as Dialog from '$lib/components/ui/dialog';
 import {locale,t} from '$lib/i18n';
 let {result,isShow}:{result:any;isShow:boolean}=$props();
 let open=$state(false),busy=$state(false),error=$state(''),message=$state(''),metadata=$state<any>(null),seasons=$state<number[]>([]),specific=$state<Record<number,boolean>>({}),episodes=$state<Record<number,number[]>>({});
 let wanted=$state('1'),minimum=$state('3');
 async function read(r:Response){const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Request could not be submitted.');return data;}
 async function show(){open=true;busy=true;error='';message='';seasons=[];specific={};episodes={};metadata=null;try{metadata=await read(await fetch(`/api/v1/requests/preview/${isShow?'tv':'movie'}/${result.metadata_provider}/${result.external_id}?language=${$locale}`));episodes=Object.fromEntries((metadata.seasons??[]).map((s:any)=>[s.number,[]]));}catch(e){error=(e as Error).message;}finally{busy=false;}}
 async function submit(e:SubmitEvent){e.preventDefault();busy=true;error='';try{const selected=Object.fromEntries(seasons.filter(n=>specific[n]).map(n=>[n,episodes[n]??[]]));await read(await fetch('/api/v1/requests/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:isShow?'tv':'movie',provider:result.metadata_provider,external_id:result.external_id,language:$locale,seasons:seasons.filter(n=>!specific[n]),episodes:selected,wanted_quality:Number(wanted),min_quality:Number(minimum)})}));message='Request submitted. You can follow its progress under Requests.';metadata=null;}catch(e){error=(e as Error).message;}finally{busy=false;}}
</script>
<Dialog.Root bind:open><Dialog.Trigger class="min-h-9 w-full rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground sm:text-sm" onclick={show}>{t($locale,isShow?'Request series':'Request movie')}</Dialog.Trigger>
<Dialog.Content class="max-h-[90vh] w-full max-w-2xl overflow-y-auto"><form onsubmit={submit} class="space-y-4 text-left">
  <div class="flex items-start justify-between gap-3"><Dialog.Title class="text-xl font-bold">{metadata?.name??result.name}</Dialog.Title><button type="button" class="rounded-lg border px-3 py-2" onclick={()=>open=false}>{t($locale,'Close')}</button></div>
  {#if busy}<p role="status">{t($locale,'Loading…')}</p>{/if}
  {#if error}<p role="alert" class="text-sm text-destructive">{t($locale,error)}</p>{/if}
  {#if message}<p role="status" class="rounded-lg bg-primary/10 p-4">{t($locale,message)}</p>{/if}
  {#if metadata}<p class="text-sm text-muted-foreground">{metadata.overview}</p>
   {#if isShow}<p class="text-sm text-muted-foreground">{t($locale,'One movie or season counts as one request. Further episodes from a previously requested season do not consume another quota unit.')}</p><div class="space-y-3">
    {#each metadata.seasons as season (season.number)}<section class="rounded-xl border p-3"><label class="flex items-center gap-2 font-medium"><input type="checkbox" bind:group={seasons} value={season.number}/>{t($locale,'Season')} {season.number} · {season.episodes.length} {t($locale,'Episodes')}</label>
    {#if seasons.includes(season.number)}<label class="mt-3 block text-sm"><input type="checkbox" bind:checked={specific[season.number]}/> {t($locale,'Select individual episodes')}</label>
     {#if specific[season.number]}<div class="mt-2 grid gap-2 sm:grid-cols-2">{#each season.episodes as episode}<label class="flex items-start gap-2 text-sm"><input type="checkbox" bind:group={episodes[season.number]} value={episode.number}/>E{episode.number} · {episode.title}</label>{/each}</div>{/if}
    {/if}</section>{/each}</div>{/if}
   <div class="grid gap-3 sm:grid-cols-2"><label class="text-sm">{t($locale,'Preferred quality')}<select bind:value={wanted} class="mt-1 w-full rounded-lg border bg-background p-2">{#each [[1,'2160p'],[2,'1080p'],[3,'720p'],[4,'480p']] as quality}<option value={String(quality[0])}>{quality[1]}</option>{/each}</select></label><label class="text-sm">{t($locale,'Minimum quality')}<select bind:value={minimum} class="mt-1 w-full rounded-lg border bg-background p-2">{#each [[1,'2160p'],[2,'1080p'],[3,'720p'],[4,'480p']] as quality}<option value={String(quality[0])}>{quality[1]}</option>{/each}</select></label></div>
   <p class="text-xs text-muted-foreground">{t($locale,'Configured release rules apply to all downloads.')}</p>
   <button disabled={busy||(isShow&&!seasons.length)||Number(wanted)>Number(minimum)} class="w-full rounded-lg bg-primary px-4 py-3 font-medium text-primary-foreground disabled:opacity-40">{t($locale,'Submit request')}</button>
  {/if}
 </form></Dialog.Content></Dialog.Root>
