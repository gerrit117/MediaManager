<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
 import {onMount} from 'svelte';
 import {locale,t} from '$lib/i18n';
 let quota=$state<any>(null);
 onMount(async()=>{try{const r=await fetch('/api/v1/requests/quota');if(r.ok)quota=await r.json();}catch{}});
</script>
{#if quota}<aside class="rounded-lg border p-3 text-sm"><strong>{t($locale,'Request quota:')}</strong> {quota.used} / {quota.limit??t($locale,'Unlimited')} {t($locale,'this month')} · {t($locale,'Approval:')} {t($locale,quota.auto_approve?'Automatic':mmT($mmLocale, "By administrator"))}.<br/>{t($locale,'New quota:')} {new Date(quota.resets_at).toLocaleDateString($locale==='de'?'de-DE':'en-GB',{timeZone:'Europe/Berlin'})}.</aside>{/if}
