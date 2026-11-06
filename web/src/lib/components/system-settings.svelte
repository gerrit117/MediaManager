<script lang="ts">
 import { onMount } from 'svelte';
 type Field = { key: string; label: string; kind: string; value: any; configured: boolean; environment: boolean };
 let fields = $state<Field[]>([]); let busy = $state(false); let message = $state(''); let failed = $state(false); let pending = $state(false);
 const groups: Record<string,string> = { misc:'Bibliothek & Pfade',metadata:'Metadaten',torrents:'Downloadmanager — NZB & Torrent',indexers:'Indexer-Dienste',database:'PostgreSQL',auth:'Anmeldung' };
 async function load() {
  try { const response = await fetch('/api/v1/settings'); if (!response.ok) throw Error('Einstellungen konnten nicht geladen werden.'); const data = await response.json(); fields=data.fields.map((f: Field) => ({...f,value:f.kind==='secret'?'':f.kind==='list'?(f.value??[]).join(', '):f.value})); pending=data.restart_required; }
  catch(e) { message=(e as Error).message; failed=true; }
 }
 onMount(load);
 async function save(event: SubmitEvent) {
  event.preventDefault(); busy=true; failed=false; message='';
  const values: Record<string,any>={};
  for(const field of fields) if(!field.environment) { if(field.kind==='secret' && !field.value) continue; values[field.key]=field.kind==='number'?Number(field.value):field.kind==='list'?String(field.value).split(',').map(x=>x.trim()).filter(Boolean):field.value; }
  try { const response=await fetch('/api/v1/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})}); const data=await response.json(); if(!response.ok) throw Error(data.detail??'Speichern fehlgeschlagen.'); message=data.message;pending=true; for(const field of fields) if(field.kind==='secret' && field.value) { field.value='';field.configured=true; } }
  catch(e) { failed=true;message=(e as Error).message; } finally { busy=false; }
 }
</script>
<section id="system" class="rounded-xl border bg-card p-5 shadow-sm">
 <h2 class="text-xl font-semibold">Einrichtung & Systemeinstellungen</h2>
 <p class="mt-2 text-sm text-muted-foreground">Containerpfade, Verbindungen und Sprache zentral verwalten. Vorhandene Konfigurationsdateien bleiben erhalten. Änderungen werden beim nächsten Containerstart aktiviert.</p>
 <p class="mt-2 text-sm text-muted-foreground">Direkte NZB-Indexer und Kategorien stehen weiter unten. Entpackungsregeln und Usenet-Zugangsdaten verwaltet derzeit SABnzbd.</p>
 {#if pending}<p role="status" class="my-3 rounded-lg border border-amber-500 p-3">Es sind Änderungen vorgemerkt. Starte den MediaManager-Container über Unraid neu, um sie zu aktivieren.</p>{/if}
 <form onsubmit={save} class="mt-4 space-y-3">
  {#each Object.entries(groups) as [group,title]}
   <details class="rounded-lg border p-4" open={group==='misc'}>
    <summary class="cursor-pointer font-semibold">{title}</summary>
    <div class="mt-4 grid min-w-0 gap-4 md:grid-cols-2">
     {#each fields.filter(f=>f.key.startsWith(group+'.')) as field (field.key)}
      <label class="flex min-w-0 flex-col gap-2 text-sm" for={'setting-'+field.key}>
       <span>{field.label}{field.environment?' · per Umgebungsvariable gesetzt':''}</span>
       {#if field.kind==='bool'}
        <input id={'setting-'+field.key} type="checkbox" class="size-5 accent-primary" bind:checked={field.value} disabled={field.environment||busy}/>
       {:else if field.kind==='number'}
        <input id={'setting-'+field.key} type="number" min="1" class="w-full min-w-0 rounded-md border bg-background p-2" bind:value={field.value} disabled={field.environment||busy}/>
       {:else}
        <input id={'setting-'+field.key} type={field.kind==='secret'?'password':'text'} autocomplete={field.kind==='secret'?'new-password':'off'} class="w-full min-w-0 rounded-md border bg-background p-2" bind:value={field.value} placeholder={field.kind==='secret'?(field.configured?'Hinterlegt — leer lassen zum Behalten':'Noch nicht hinterlegt'):''} disabled={field.environment||busy}/>
       {/if}
      </label>
     {/each}
    </div>
   </details>
  {/each}
  {#if message}<p role="status" class:text-destructive={failed}>{message}</p>{/if}
  <button type="submit" disabled={busy||!fields.length} class="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground disabled:opacity-50">{busy?'Speichert …':'Änderungen vormerken'}</button>
 </form>
</section>
