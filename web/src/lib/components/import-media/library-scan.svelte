<script lang="ts">
 import { getContext } from 'svelte';
 import {locale, t} from '$lib/i18n';
 let {kind}: {kind:'movies'|'tv'}=$props();
 const user=getContext<()=>{is_superuser:boolean}>('user');
 const scan=getContext<{run:(kind:'movies'|'tv')=>Promise<void>;busy:(kind:'movies'|'tv')=>boolean;status:(kind:'movies'|'tv')=>string}>('libraryScan');
</script>
{#if user()?.is_superuser}
 <section class="space-y-2 rounded-xl border p-4" aria-label={t($locale,'Library scan')}>
  <button class="rounded-md bg-primary px-4 py-2 text-primary-foreground" disabled={scan.busy(kind)} onclick={()=>scan.run(kind)}>{t($locale,scan.busy(kind)?'Scanning library…':'Scan existing library')}</button>
  <p class="text-sm text-muted-foreground">{t($locale,'Find existing media directories. Choose catalogue-only or reorganize for each import.')}</p>
  {#if scan.status(kind)}<p role="status">{t($locale,scan.status(kind))}</p>{/if}
 </section>
{/if}
