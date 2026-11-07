<script lang="ts">
 import {locale,t} from '$lib/i18n';
 import {onMount} from 'svelte';
 import {toast} from 'svelte-sonner';
 import client from '$lib/api';
 import type {components} from '$lib/api/api';
 let {media,mediaType}:{media:components['schemas']['PublicShow']|components['schemas']['PublicMovie'];mediaType:'tv'|'movie'}=$props();
 let libraries=$state<{name:string;path:string}[]>([]);let busy=$state(false);
 let value=$derived(media.library||'Default');
 onMount(async()=>{const r=await fetch(mediaType==='tv'?'/api/v1/tv/shows/libraries':'/api/v1/movies/libraries');if(r.ok)libraries=await r.json();});
 async function select(event:Event){
  const selected=(event.currentTarget as HTMLSelectElement).value;busy=true;
  const endpoint=mediaType==='tv'?`/api/v1/tv/shows/${media.id}/library`:`/api/v1/movies/${media.id}/library`;
  try{const r=await fetch(endpoint+'?'+new URLSearchParams({library:selected}),{method:'POST'});if(!r.ok)throw Error();media.library=selected;toast.success(t($locale,'Import destination updated'));}
  catch{toast.error(t($locale,'Failed to update library'));(event.target as HTMLSelectElement).value=value;}finally{busy=false;}
 }
</script>
<div class="w-full space-y-2 rounded-xl border p-3">
 <label class="block text-sm font-semibold">{t($locale,'Import destination')}
 <select class="mt-2 w-full rounded-lg border bg-background p-2" {value} onchange={select} disabled={busy}>
 {#if !libraries.some(l=>l.name==='Default')}<option value="Default">{t($locale,'Default')}</option>{/if}
 {#each libraries as library}<option value={library.name}>{library.name} — {library.path}</option>{/each}
 </select></label>
 <p class="text-xs text-muted-foreground">{t($locale,'Used for future imports. Existing files stay in place. To correct a title or provider ID, use metadata editing.')}</p>
</div>
