<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
 import {onMount} from 'svelte';
 import NewznabSettings from '$lib/components/newznab-settings.svelte';
 import IndexerCategories from '$lib/components/indexer-categories.svelte';
 let selected=$state('integrated');let revision=$state(0);let fields=$state<any[]>([]);let busy=$state(false);let message=$state('');
 const providers=[{id:'integrated',name:'Integriert'},{id:'prowlarr',name:'Prowlarr'},{id:'jackett',name:'Jackett'}];
 onMount(async()=>{try{const r=await fetch('/api/v1/settings');if(!r.ok)throw Error('Einstellungen konnten nicht geladen werden.');fields=(await r.json()).fields.filter((f:any)=>f.key.startsWith('indexers.')).map((f:any)=>({...f,value:f.kind==='secret'?'':f.kind==='list'?(f.value??[]).join(', '):f.value}));}catch(e){message=(e as Error).message;}});
 async function save(e:SubmitEvent){e.preventDefault();busy=true;message='';const values:Record<string,any>={};for(const f of fields.filter(f=>f.key.startsWith('indexers.'+selected+'.')&&!f.environment)){if(f.kind==='secret'&&!f.value)continue;values[f.key]=f.kind==='list'?f.value.split(',').map((x:string)=>x.trim()).filter(Boolean):f.kind==='number'?Number(f.value):f.value;}
  try{const r=await fetch('/api/v1/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});const data=await r.json();if(!r.ok)throw Error(data.detail??'Speichern fehlgeschlagen.');message=data.message;for(const f of fields)if(f.kind==='secret'&&f.value){f.value='';f.configured=true;}revision++;}catch(e){message=(e as Error).message;}finally{busy=false;}
 }
</script>
<section class="space-y-4">
 <h2 class="text-2xl font-semibold">{mmT($mmLocale, "Indexer-Dienste" )}</h2>
 <div role="tablist" aria-label={mmT($mmLocale, "Indexer-Dienste")} class="flex flex-wrap gap-2 rounded-lg border bg-card p-2">
  {#each providers as provider}<button type="button" role="tab" aria-selected={selected===provider.id} class="rounded-md px-4 py-2 aria-selected:bg-primary aria-selected:text-primary-foreground" onclick={()=>{selected=provider.id;message='';}}>{mmT($mmLocale, provider.name)}</button>{/each}
 </div>
 <div hidden={selected!=='integrated'}><NewznabSettings onSaved={()=>revision++}/></div>
 {#if selected!=='integrated'}
 <form onsubmit={save} class="space-y-4 rounded-xl border bg-card p-5">
  <h3 class="text-xl font-semibold">{selected==='prowlarr'?'Prowlarr':'Jackett'}</h3>
  <div class="grid gap-4 md:grid-cols-2">
  {#each fields.filter(f=>f.key.startsWith('indexers.'+selected+'.')) as field (field.key)}
   <label class="flex min-w-0 flex-col gap-2 text-sm" for={'indexer-'+field.key}><span>{mmT($mmLocale, field.label)}</span>
    {#if field.kind==='bool'}<input id={'indexer-'+field.key} type="checkbox" bind:checked={field.value} disabled={field.environment||busy} class="size-5"/>
    {:else}<input id={'indexer-'+field.key} type={field.kind==='secret'?'password':field.kind==='number'?'number':'text'} autocomplete={field.kind==='secret'?'new-password':'off'} bind:value={field.value} disabled={field.environment||busy} class="w-full min-w-0 rounded-md border bg-background p-2" placeholder={field.kind==='secret'&&field.configured?mmT($mmLocale, "Hinterlegt — leer lassen zum Behalten"):''}/>{/if}
   </label>
  {/each}
  </div><button type="submit" class="rounded-md bg-primary px-4 py-2 text-primary-foreground" disabled={busy||!fields.length}>{mmT($mmLocale, "Verbindung speichern" )}</button>
  {#if message}<p role="status">{mmT($mmLocale, message)}</p>{/if}
 </form>
 {/if}
 {#key selected+revision}<IndexerCategories providerFilter={selected==='integrated'?'newznab':selected}/>{/key}
</section>
