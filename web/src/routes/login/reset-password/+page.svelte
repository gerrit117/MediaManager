<script lang="ts">
 import {passwordHint,validPassword} from '$lib/password-policy';
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import client from '$lib/api';
	import { resolve } from '$app/paths';

	let newPassword = $state('');
	let confirmPassword = $state('');
	let isLoading = $state(false);
	let resetToken = $state('');

	onMount(() => {
        resetToken=new URLSearchParams(location.hash.slice(1)).get('token')||page.data.token||'';
        history.replaceState({},'',location.pathname);
		if (!resetToken) {
			toast.error('Invalid or missing reset token.');
			goto(resolve('/login', {}));
		}
	});

	async function resetPassword() {
        if(!validPassword(newPassword)){toast.error(mmT($mmLocale,passwordHint));return;}
		if (newPassword !== confirmPassword) {
			toast.error('Passwords do not match.');
			return;
		}

		if (!resetToken) {
			toast.error('Invalid or missing reset token.');
			return;
		}

		isLoading = true;

		const { response } = await client.POST('/api/v1/auth/reset-password', {
			body: {
				password: newPassword,
				token: resetToken
			}
		});

		if (response.ok) {
			toast.success('Password reset successfully! You can now log in with your new password.');
			goto(resolve('/login', {}));
		} else {
			toast.error(`Failed to reset password`);
		}
		isLoading = false;
	}

	const handleSubmit = (event: Event) => {
		event.preventDefault();
		resetPassword();
	};
</script>
<p class="my-2 text-xs text-muted-foreground">{mmT($mmLocale,passwordHint)}</p>

<svelte:head>
<meta name="referrer" content="no-referrer"/>
	<title>{mmT($mmLocale, "Reset Password - MediaManager" )}</title>
	<meta content="Reset your MediaManager password with a secure token" name="description" />
</svelte:head>

<Card class="mx-auto max-w-sm">
	<CardHeader>
		<CardTitle class="text-2xl">{mmT($mmLocale, "Reset Password" )}</CardTitle>
		<CardDescription>{mmT($mmLocale, "Enter your new password below." )}</CardDescription>
	</CardHeader>
	<CardContent>
		<form class="grid gap-4" onsubmit={handleSubmit}>
			<div class="grid gap-2">
				<Label for="new-password">{mmT($mmLocale, "New Password" )}</Label>
				<Input
					bind:value={newPassword}
					disabled={isLoading}
					id="new-password"
					minlength={8}
					placeholder={mmT($mmLocale, "Enter your new password")}
					required
					type="password"
				/>
			</div>
			<div class="grid gap-2">
				<Label for="confirm-password">{mmT($mmLocale, "Confirm Password" )}</Label>
				<Input
					bind:value={confirmPassword}
					disabled={isLoading}
					id="confirm-password"
					minlength={8}
					placeholder={mmT($mmLocale, "Confirm your new password")}
					required
					type="password"
				/>
			</div>
			<Button class="w-full" disabled={isLoading || !newPassword || !confirmPassword} type="submit">
				{#if isLoading}
					{mmT($mmLocale, "Resetting Password..." )}
				{:else}
					{mmT($mmLocale, "Reset Password" )}
				{/if}
			</Button>
		</form>
		<div class="mt-4 text-center text-sm">
			<a class="font-semibold text-primary hover:underline" href={resolve('/login', {})}>
				{mmT($mmLocale, "Back to Login" )}
			</a>
			<span class="mx-2 text-muted-foreground">•</span>
			<a class="text-primary hover:underline" href={resolve('/login/forgot-password', {})}>
				{mmT($mmLocale, "Request New Reset Link" )}
			</a>
		</div>
	</CardContent>
</Card>
