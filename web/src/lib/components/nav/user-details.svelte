<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { getContext } from 'svelte';
	import type { components } from '$lib/api/api';
	const user: () => components['schemas']['UserRead'] = getContext('user');
</script>

<span class="truncate font-semibold">{user().email}</span>
{#if user().is_superuser}
	<span class="truncate text-xs">{mmT($mmLocale, "Administrator" )}</span>
{:else}
	<span class="truncate text-xs">{mmT($mmLocale, "User" )}</span>
{/if}
