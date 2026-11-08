<script lang="ts">
import {locale,t} from '$lib/i18n';
import * as Sidebar from '$lib/components/ui/sidebar';
import RequestCenter from '$lib/components/requests/request-center.svelte';
</script>
<svelte:head><title>{t($locale,'Requests')} – MediaManager</title></svelte:head>
<header class="flex h-16 items-center gap-3 px-4"><Sidebar.Trigger/><span class="text-sm text-muted-foreground">MediaManager / {t($locale,'Requests')}</span></header>
<main class="mx-auto w-full min-w-0 max-w-[90rem] space-y-5 p-4"><h1 class="text-3xl font-bold">{t($locale,'Requests')}</h1><RequestCenter kind="movie"/></main>
