<script lang="ts">
 import {getContext} from 'svelte';
 import {resolve} from '$app/paths';
 import {locale,t} from '$lib/i18n';
 import {FolderSearch,Settings2} from 'lucide-svelte';
 let {kind}:{kind:'movies'|'tv'}=$props();
 const user=getContext<()=>{is_superuser:boolean}>('user');
 const scan=getContext<{run:(kind:'movies'|'tv')=>Promise<void>;busy:(kind:'movies'|'tv')=>boolean;status:(kind:'movies'|'tv')=>string}>('libraryScan');
</script>
{#if user()?.is_superuser}
 <section class="flex flex-wrap items-center justify-end gap-2" aria-label={t($locale,'Library scan')}>
  <button class="inline-flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-sm hover:bg-muted" disabled={scan.busy(kind)} onclick={()=>scan.run(kind)}><FolderSearch class="size-4"/>{t($locale,scan.busy(kind)?'Scanning library…':'Match individual directories')}</button>
  <a class="inline-flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-sm hover:bg-muted" href={resolve('/dashboard/settings',{})+'?section=library'}><Settings2 class="size-4"/>{t($locale,'Manage existing library')}</a>
  {#if scan.status(kind)}<p role="status" class="w-full text-right text-xs text-muted-foreground">{t($locale,scan.status(kind))}</p>{/if}
 </section>
{/if}
