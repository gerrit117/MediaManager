<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { UserCheck } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { handleLogout } from '$lib/utils.ts';
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Verify Account - MediaManager" )}</title>
	<meta content="Verify your MediaManager account to complete registration" name="description" />
</svelte:head>

<div class="absolute top-4 right-4">
	<Button onclick={() => handleLogout()} variant="outline">{mmT($mmLocale, "Logout" )}</Button>
</div>
<div class="mx-auto w-full max-w-md text-center">
	<div class="mb-6">
		<UserCheck class="mx-auto h-16 w-16 text-primary" />
	</div>
	<h1 class="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
		{mmT($mmLocale, "Account Pending Activation" )}
	</h1>
	<p class="mt-4 text-lg text-muted-foreground">
		{mmT($mmLocale, "Your account has been successfully created, but activation by an administrator is required." )}
	</p>
	<div class="mt-8">
		<Button onclick={() => handleLogout()}>{mmT($mmLocale, "Logout" )}</Button>
	</div>
	<p class="end mt-10 text-sm text-muted-foreground">
		{mmT($mmLocale, "If you have any questions, please contact an administrator." )}
	</p>
</div>
