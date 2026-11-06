<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import type { LayoutProps } from './$types';

	let { data, children }: LayoutProps = $props();

	const showData = $derived(data.showData);
	const fetchError = $derived((data as { error?: string }).error || null);
</script>

{#if fetchError}
	<p>{mmT($mmLocale, "Error loading show:" )} {fetchError}</p>
{:else if showData}
	{@render children()}
{:else}
	<p>{mmT($mmLocale, "Loading show data..." )}</p>
{/if}
