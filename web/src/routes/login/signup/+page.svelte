<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import SignupCard from '$lib/components/auth/signup-card.svelte';
	import { page } from '$app/state';

	let oauthProviders: string[] = $derived(page.data.oauthProviders);
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Login - MediaManager" )}</title>
	<meta content="Signup - MediaManager" name="description" />
</svelte:head>

<SignupCard oauthProviderNames={oauthProviders} />
