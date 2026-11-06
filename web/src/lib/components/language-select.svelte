<script lang="ts">
 import {locale,setLanguage,type Language} from '$lib/i18n';
</script>
<label class="flex items-center gap-3 text-sm"><span>{$locale==='de'?'Sprache':'Language'}</span><select aria-label={$locale==='de'?'Sprache':'Language'} value={$locale} onchange={(e)=>setLanguage(e.currentTarget.value as Language)} class="rounded-lg border bg-background px-3 py-2"><option value="de">{'Deutsch'}</option><option value="en">{'English'}</option></select></label>
