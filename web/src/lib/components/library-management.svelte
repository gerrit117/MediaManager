<script lang="ts">
 import {onMount} from 'svelte';
 import {invalidateAll} from '$app/navigation';
 import {resolve} from '$app/paths';
 import {locale,t} from '$lib/i18n';
 let {active=false}:{active?:boolean}=$props();
 let fields=$state<any[]>([]),summary=$state<any>(null),job=$state<any>({status:'idle'}),busy=$state(false),message=$state(''),failed=$state(false),mode=$state('catalogue');
 async function refresh(){try{const [a,b]=await Promise.all([fetch('/api/v1/library/scan'),fetch('/api/v1/library/summary')]);if(!a.ok||!b.ok)throw Error('Library status could not be loaded.');const previous=job.status;job=await a.json();summary=await b.json();if(previous==='running'&&job.status!=='running')await invalidateAll();}catch(e){failed=true;message=(e as Error).message;}}
 onMount(()=>{void refresh();void load();const timer=setInterval(()=>{if(active||job.status==='running')void refresh();},2000);return()=>clearInterval(timer);});
 async function load(){try{const r=await fetch('/api/v1/settings');if(!r.ok)throw Error('Einstellungen konnten nicht geladen werden.');fields=(await r.json()).fields.filter((f:any)=>f.key.startsWith('misc.library_scan.')).map((f:any)=>({...f,value:f.kind==='secret'?'':f.value}));}catch(e){failed=true;message=(e as Error).message;}}
 async function save(e:SubmitEvent){e.preventDefault();busy=true;failed=false;message='';try{const values=Object.fromEntries(fields.filter(f=>!f.environment&&!(f.kind==='secret'&&!f.value)).map(f=>[f.key,f.kind==='number'?Number(f.value):f.value]));const r=await fetch('/api/v1/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});const result=await r.json();if(!r.ok)throw Error(result.detail??'Speichern fehlgeschlagen.');message=result.message;for(const field of fields)if(field.kind==='secret'&&field.value){field.configured=true;field.value='';}}catch(e){failed=true;message=(e as Error).message;}finally{busy=false;}}
 async function start(){if(mode==='reorganize'&&!confirm(t($locale,'Reorganize the existing library? This renames source folders and uses the file importer. Continue only if you want to change the media layout.')))return;busy=true;failed=false;message='';try{const r=await fetch('/api/v1/library/scan?mode='+mode+'&confirm_reorganize='+(mode==='reorganize'),{method:'POST'});const result=await r.json();if(!r.ok)throw Error(result.detail??'Library scan could not be started.');await refresh();}catch(e){failed=true;message=(e as Error).message;}finally{busy=false;}}
 const names:Record<string,string>={idle:'Ready',running:'Scanning library…',completed:'Completed',failed:'Failed',interrupted:'Interrupted'};
</script>
<section class="space-y-5 rounded-xl border bg-card p-5">
 <h2 class="text-2xl font-semibold">{t($locale,'Library')}</h2>
 <p class="text-sm text-muted-foreground">{t($locale,'Register existing movies and shows in the database. Trusted NFO IDs and optional Sonarr/Radarr metadata identify titles; uncertain matches are left for review. This does not request new downloads.')}</p>
 <div class="grid min-w-0 gap-3 sm:grid-cols-2">
  <article class="rounded-lg border p-4"><strong>{summary?.movies??0} {t($locale,'Movies')}</strong><p class="mt-2 break-all text-xs text-muted-foreground">{summary?.paths?.movies??'…'}</p></article>
  <article class="rounded-lg border p-4"><strong>{summary?.shows??0} {t($locale,'TV Shows')}</strong><p class="mt-2 break-all text-xs text-muted-foreground">{summary?.paths?.tv??'…'}</p></article>
 </div>
 <div class="space-y-3 rounded-xl border p-4">
  <h3 class="font-semibold">{t($locale,'Import existing library')}</h3>
  <label class="block space-y-2"><span>{t($locale,'Import mode')}</span><select aria-label={t($locale,'Import mode')} class="w-full rounded-lg border bg-background p-3" bind:value={mode} disabled={busy||job.status==='running'}><option value="catalogue">{t($locale,'Catalogue only (keep files in place)')}</option><option value="reorganize">{t($locale,'Reorganize into library folders')}</option></select></label>
  <p class="text-sm text-muted-foreground">{t($locale,mode==='catalogue'?'Records existing video files without moving, renaming or extracting archives.':'Uses the existing import process, including archive extraction and folder renaming.')}</p>
  <button type="button" class="rounded-lg bg-primary px-4 py-2 text-primary-foreground" disabled={busy||job.status==='running'} onclick={start}>{t($locale,'Start library scan and import')}</button>
 </div>
 <div class="space-y-2 rounded-xl border p-4" aria-live="polite">
  <p class="font-semibold">{t($locale,names[job.status]??job.status)}</p>
  {#if job.total}<progress class="h-3 w-full" max={job.total} value={job.processed??0}></progress><p>{job.processed} / {job.total} · {job.imported??0} {t($locale,'catalogued or updated')} · {job.skipped??0} {t($locale,'without video files')}</p>{/if}
  {#if job.current}<p class="break-all text-sm text-muted-foreground">{job.current}</p>{/if}
  {#if job.review?.length}<details class="rounded-lg border p-3"><summary class="cursor-pointer font-medium">{t($locale,'Needs manual matching')}: {job.review.length}</summary><ul class="mt-3 space-y-3">{#each job.review as row}<li class="space-y-1 border-b pb-3"><p class="break-all text-sm">{row.directory}</p><p class="text-xs text-muted-foreground">{t($locale,row.reason)}</p><a class="inline-flex rounded border px-3 py-1 text-sm" href={resolve(row.kind==='movies'?'/dashboard/movies':'/dashboard/tv',{})+'?match='+encodeURIComponent(row.directory)}>{t($locale,'Match manually')}</a></li>{/each}</ul></details>{/if}
  {#if job.errors?.length}<details class="rounded-lg border border-destructive p-3"><summary class="cursor-pointer font-medium">{t($locale,'Errors')}: {job.errors.length}</summary>{#each job.errors as row}<p class="mt-2 break-all text-sm">{row.source??row.directory??''}: {t($locale,row.message)}</p>{/each}</details>{/if}
 </div>
 <form onsubmit={save} class="space-y-4 rounded-xl border p-4">
  <h3 class="font-semibold">{t($locale,'Scan settings')}</h3>
  <p class="text-sm text-muted-foreground">{t($locale,'Automatic scans always catalogue in place. Existing monitoring settings and file permissions are preserved. Source API access is read-only; API keys stay on the server.')}</p>
  <div class="grid min-w-0 gap-4 md:grid-cols-2">
   {#each fields as field (field.key)}
    <label class="flex min-w-0 flex-col gap-2 text-sm" for={'library-'+field.key}><span>{t($locale,field.label)}</span>
     {#if field.kind==='bool'}<input id={'library-'+field.key} type="checkbox" bind:checked={field.value} disabled={busy||field.environment} class="size-5"/>
     {:else}<input id={'library-'+field.key} class="w-full min-w-0 rounded-lg border bg-background p-3" type={field.kind==='secret'?'password':field.kind==='number'?'number':'text'} min={field.kind==='number'?1:undefined} max={field.kind==='number'?168:undefined} autocomplete={field.kind==='secret'?'new-password':'off'} bind:value={field.value} disabled={busy||field.environment} placeholder={field.kind==='secret'?(field.configured?t($locale,'Hinterlegt — leer lassen zum Behalten'):t($locale,'Noch nicht hinterlegt')):''}/>{/if}
    </label>
   {/each}
  </div>
  <button type="submit" class="rounded-lg border px-4 py-2" disabled={busy||!fields.length}>{t($locale,'Save scan settings')}</button>
 </form>
 {#if message}<p role="status" class:text-destructive={failed}>{t($locale,message)}</p>{/if}
</section>
