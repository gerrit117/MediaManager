<script lang="ts">
 import {getFullyQualifiedMediaName} from '$lib/utils';
 import {env} from '$env/dynamic/public';
 import {onMount} from 'svelte';
 import {ImageOff} from 'lucide-svelte';
 let {media,version='',eager=false}:{media:any;version?:string|number;eager?:boolean}=$props();
 let attempt=$state(0),updated=$state(0);
 onMount(()=>{const refresh=()=>updated=Date.now();addEventListener('mediamanager-poster-updated',refresh);return()=>removeEventListener('mediamanager-poster-updated',refresh);});
 const formats=['jpeg','webp','jpg','avif'];
 let identity=$derived(String(media.id)+':'+version+':'+updated);
 $effect(()=>{identity;attempt=0;});
 let url=$derived((env.PUBLIC_API_URL??'').replace(/\/$/,'')+'/api/v1/static/image/'+media.id+'.'+formats[attempt]+(updated||version?'?v='+(updated||version):''));
</script>
<div class="media-poster relative block aspect-[2/3] w-full overflow-hidden rounded-xl bg-muted">
 {#if media.id&&attempt<formats.length}
  <img src={url} alt={getFullyQualifiedMediaName(media)} class="absolute inset-0 h-full w-full object-cover" loading={eager?'eager':'lazy'} decoding="async" onerror={()=>attempt+=1}/>
 {:else}
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-gradient-to-br from-muted to-background p-4 text-center text-muted-foreground"><ImageOff class="size-10 opacity-40"/><span class="line-clamp-3 text-sm font-medium">{media.name}</span></div>
 {/if}
</div>
