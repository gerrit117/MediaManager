<script lang="ts">
 import {onMount} from 'svelte';
 import {locale,t} from '$lib/i18n';
 let fields=$state<any[]>([]),busy=$state(false),message=$state(''),failed=$state(false);
 onMount(async()=>{try{const r=await fetch('/api/v1/settings');if(!r.ok)throw Error('Einstellungen konnten nicht geladen werden.');fields=(await r.json()).fields.filter((f:any)=>f.key.startsWith('indexers.release_policy.')).map((f:any)=>({...f,value:f.kind==='list'?f.value.join(', '):f.value}));}catch(e){failed=true;message=(e as Error).message;}});
 function move(field:any,index:number,delta:number){const values=field.value.split(',').map((v:string)=>v.trim()).filter(Boolean);[values[index],values[index+delta]]=[values[index+delta],values[index]];field.value=values.join(', ');}
 async function save(event:SubmitEvent){event.preventDefault();busy=true;failed=false;message='';try{const values=Object.fromEntries(fields.filter(f=>!f.environment).map(f=>[f.key,f.kind==='list'?f.value.split(',').map((x:string)=>x.trim()).filter(Boolean):f.value]));const r=await fetch('/api/v1/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});const result=await r.json();if(!r.ok)throw Error(result.detail??'Speichern fehlgeschlagen.');message=result.message;}catch(e){message=(e as Error).message;failed=true;}finally{busy=false;}}
</script>
<section class="space-y-4 rounded-xl border bg-card p-5">
 <h2 class="text-2xl font-semibold">{t($locale,'Release rules')}</h2>
 <p class="text-sm text-muted-foreground">{t($locale,'Applies to integrated indexers, Prowlarr and Jackett, for manual and automatic NZB/torrent downloads. Language takes precedence over resolution; the first entry has highest priority.')}</p>
 <form onsubmit={save} class="space-y-5">
  {#each fields as field (field.key)}
   <div class="min-w-0 space-y-2 rounded-lg border p-4">
    <label for={'release-'+field.key} class="flex items-center gap-3 font-medium">
     {#if field.kind==='bool'}<input id={'release-'+field.key} type="checkbox" class="size-5" bind:checked={field.value} disabled={busy||field.environment}/>{/if}
     {t($locale,field.label)}
    </label>
    {#if field.kind==='list'}
     {#if !field.key.endsWith('excluded_tags')}
      <ol class="space-y-2">
       {#each field.value.split(',').map((v:string)=>v.trim()).filter(Boolean) as value,index}
        <li class="flex items-center justify-between gap-3 rounded-lg bg-muted px-3 py-2"><span>{index+1}. {value==='de'?t($locale,'German'):value==='en'?t($locale,'English'):value}</span><div class="flex gap-2"><button type="button" aria-label={t($locale,'Higher priority')+' '+value} disabled={busy||field.environment||index===0} class="rounded border px-3 py-1 disabled:opacity-30" onclick={()=>move(field,index,-1)}>↑</button><button type="button" aria-label={t($locale,'Lower priority')+' '+value} disabled={busy||field.environment||index===field.value.split(',').filter((v:string)=>v.trim()).length-1} class="rounded border px-3 py-1 disabled:opacity-30" onclick={()=>move(field,index,1)}>↓</button></div></li>
       {/each}
      </ol>
     {/if}
     <input id={'release-'+field.key} class="w-full min-w-0 rounded-lg border bg-background p-3" bind:value={field.value} disabled={busy||field.environment}/>
    {/if}
   </div>
  {/each}
  <p class="text-sm text-muted-foreground">{t($locale,'Release names provide language/source hints, not verified audio tracks. Unknown languages require explicit permission. Changes apply immediately; existing files and queued downloads are not replaced merely by saving.')}</p>
  {#if message}<p role="status" class:text-destructive={failed}>{t($locale,message)}</p>{/if}
  <button type="submit" disabled={busy||!fields.length} class="rounded-lg bg-primary px-4 py-2 text-primary-foreground">{t($locale,busy?'Speichert …':'Save release rules')}</button>
 </form>
</section>
