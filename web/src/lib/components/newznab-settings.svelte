<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { onMount } from 'svelte';
	import { env } from '$env/dynamic/public';
	import * as Card from '$lib/components/ui/card/index.js';

	let { onSaved }: { onSaved?: () => void } = $props();
	let url = $state('https://treasure-maps.com/api');
	let enabled = $state(false);
	let apiKey = $state('');
	let hasKey = $state(false);
	let busy = $state(true);
	let message = $state('');
	let error = $state('');
	const endpoint = `${env.PUBLIC_API_URL ?? ''}/api/v1/indexers/newznab`;

	async function load() {
		try {
			const response = await fetch(endpoint, { credentials: 'include' });
			if (!response.ok) throw new Error('Could not load the indexer settings.');
			const settings = await response.json();
			url = settings.url;
			enabled = settings.enabled;
			hasKey = settings.has_api_key;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not load settings.';
		} finally {
			busy = false;
		}
	}

	async function submit(test: boolean) {
		busy = true;
		error = '';
		message = '';
		try {
			const response = await fetch(test ? `${endpoint}/test` : endpoint, {
				method: test ? 'POST' : 'PUT',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ enabled, url, api_key: apiKey })
			});
			const result = await response.json();
			if (!response.ok) {
				throw new Error(
					typeof result.detail === 'string'
						? result.detail
						: 'Check the indexer settings and try again.'
				);
			}
			if (test) {
				message = mmT($mmLocale,result.message)+' '+mmT($mmLocale,'Available categories: {count}'.replace('{count}',String(result.categories)));
			} else {
				url = result.url;
				enabled = result.enabled;
				hasKey = result.has_api_key;
				apiKey = '';
				message = enabled
					? 'Saved. Direct searches are enabled.'
					: 'Saved. Direct searches are disabled.';
				onSaved?.();
			}
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'The indexer request failed.';
		} finally {
			busy = false;
		}
	}

	onMount(load);
</script>

<Card.Root id="newznab">
	<Card.Header>
		<Card.Title>{mmT($mmLocale, "Integrierter Indexer · Newznab (NZB)" )}</Card.Title>
		<Card.Description>
			{mmT($mmLocale, "Connect directly through the Newznab API. Prowlarr and Jackett are optional. Choose movie and TV categories below after saving the connection." )}
		</Card.Description>
	</Card.Header>
	<Card.Content>
		<form
			class="space-y-4"
			onsubmit={(event) => {
				event.preventDefault();
				submit(false);
			}}
		>
			<label class="flex items-center gap-3">
				<input type="checkbox" bind:checked={enabled} disabled={busy} />
				<span>{mmT($mmLocale, "Enable direct searches" )}</span>
			</label>
			<div class="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2">
				<label class="flex min-w-0 flex-col gap-2">
					<span>{mmT($mmLocale, "API URL" )}</span>
					<input
						type="url"
						required
						bind:value={url}
						disabled={busy}
						class="w-full min-w-0 rounded-md border bg-background p-2"
					/>
				</label>
				<label class="flex min-w-0 flex-col gap-2">
					<span>{mmT($mmLocale, "API key" )}</span>
					<input
						type="password"
						bind:value={apiKey}
						disabled={busy}
						autocomplete="new-password"
						placeholder={hasKey ? 'Saved — leave blank to keep' : 'Enter your indexer API key'}
						class="w-full min-w-0 rounded-md border bg-background p-2"
					/>
				</label>
			</div>
			<p class="text-sm text-muted-foreground">
				{hasKey ? 'An API key is stored securely on the server.' : 'No API key is stored yet.'}
				{mmT($mmLocale, "The connection test verifies your key with a search and starts no download." )}
			</p>
			<div class="flex flex-wrap gap-3">
				<button
					type="button"
					onclick={() => submit(true)}
					disabled={busy}
					class="rounded-md border px-4 py-2">{mmT($mmLocale, "Test connection" )}</button
				>
				<button
					type="submit"
					disabled={busy}
					class="rounded-md bg-primary px-4 py-2 text-primary-foreground">{mmT($mmLocale, "Save connection" )}</button
				>
			</div>
			<p role="status">{mmT($mmLocale, message)}</p>
			{#if error}<p role="alert" class="text-destructive">{mmT($mmLocale,error)}</p>{/if}
		</form>
	</Card.Content>
</Card.Root>
