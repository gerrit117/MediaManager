<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import {passwordHint,validPassword} from '$lib/password-policy';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { toast } from 'svelte-sonner';
	import * as Alert from '$lib/components/ui/alert';
	import AlertCircleIcon from '@lucide/svelte/icons/alert-circle';
	import LoadingBar from '$lib/components/loading-bar.svelte';
	import CheckCircle2Icon from '@lucide/svelte/icons/check-circle-2';
	import { handleOauth } from '$lib/utils.ts';
	import client from '$lib/api';
	import { resolve } from '$app/paths';

	let email = $state('');
    let invitationCode=$state('');
	let password = $state('');
	let errorMessage = $state('');
	let successMessage = $state('');
	let isLoading = $state(false);
	let confirmPassword = $state('');
	let {
		oauthProviderNames
	}: {
		oauthProviderNames: string[];
	} = $props();

	async function handleSignup(event: Event) {
		event.preventDefault();

		isLoading = true;
		errorMessage = '';
		successMessage = '';
        if(password!==confirmPassword||!validPassword(password)){errorMessage=password!==confirmPassword?'Passwords do not match.':passwordHint;isLoading=false;return;}
        let response;try{response=await fetch('/api/v1/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,invitation_code:invitationCode.toUpperCase()})});}catch{errorMessage='Registration failed';isLoading=false;return;}
		isLoading = false;

		if (response.ok) {
			successMessage = 'Account created. Please confirm your email address before signing in.';
			toast.success(mmT($mmLocale,successMessage));
		} else {
			const data=await response.json();errorMessage=typeof data.detail==='string'?data.detail:'Registration failed';toast.error(mmT($mmLocale,errorMessage));
		}
	}
</script>

<Card.Root class="mx-auto max-w-sm">
	<Card.Header>
		<Card.Title class="text-xl">{mmT($mmLocale, "Sign Up" )}</Card.Title>
		<Card.Description>{mmT($mmLocale, "Enter your information to create an account" )}</Card.Description>
	</Card.Header>
	<Card.Content>
		<form class="grid gap-4" onsubmit={handleSignup}>
            <label class="grid gap-2 text-sm">{mmT($mmLocale,'Invitation code')}<input required minlength="5" maxlength="5" pattern="[A-Za-z0-9]{5}" autocomplete="off" bind:value={invitationCode} class="rounded-md border bg-background p-2 uppercase"/></label>
            <p class="text-xs text-muted-foreground">{mmT($mmLocale,passwordHint)}</p>
			<div class="grid gap-2">
				<Label for="email">{mmT($mmLocale, "Email" )}</Label>
				<Input
					autocomplete="email"
					bind:value={email}
					id="email"
					placeholder="m@example.com"
					required
					type="email"
				/>
			</div>
			<div class="grid gap-2">
				<Label for="password">{mmT($mmLocale, "Password" )}</Label>
				<Input
					autocomplete="new-password"
					bind:value={password}
					id="password"
                    minlength={8}
					required
					type="password"
				/>
			</div>
			<div class="grid gap-2">
				<Label for="password">{mmT($mmLocale, "Confirm Password" )}</Label>
				<Input
					autocomplete="new-password"
					bind:value={confirmPassword}
					id="confirm-password"
					required
					type="password"
				/>
			</div>
			{#if errorMessage}
				<Alert.Root variant="destructive">
					<AlertCircleIcon class="size-4" />
					<Alert.Title>{mmT($mmLocale, "Error" )}</Alert.Title>
					<Alert.Description>{mmT($mmLocale, errorMessage)}</Alert.Description>
				</Alert.Root>
			{/if}
			{#if successMessage}
				<Alert.Root variant="default">
					<CheckCircle2Icon class="size-4" />
					<Alert.Title>{mmT($mmLocale, "Success" )}</Alert.Title>
					<Alert.Description>{mmT($mmLocale,successMessage)}</Alert.Description>
				</Alert.Root>
			{/if}
			{#if isLoading}
				<LoadingBar />
			{/if}
			<Button
				class="w-full"
				disabled={isLoading || password !== confirmPassword || password === ''}
				type="submit"
				>{mmT($mmLocale, "Create an account" )}
			</Button>
		</form>
		{#each oauthProviderNames as name (name)}
			<div
				class="relative mt-2 text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border"
			>
				<span class="relative z-10 bg-background px-2 text-muted-foreground">
					{mmT($mmLocale, "Or continue with" )}
				</span>
			</div>
			<Button class="mt-2 w-full" onclick={() => handleOauth()} variant="outline"
				>{mmT($mmLocale, "Login with" )} {name}</Button
			>
		{/each}
		<div class="mt-4 text-center text-sm">
			<Button href={resolve('/login/', {})} variant="link">{mmT($mmLocale, "Already have an account? Login" )}</Button>
		</div>
	</Card.Content>
</Card.Root>
