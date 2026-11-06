<script lang="ts">
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import type { components } from '$lib/api/api';
	import { Switch } from '$lib/components/ui/switch';
	import { Label } from '$lib/components/ui/label';
	import client from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { invalidateAll } from '$app/navigation';

	let {
		torrent
	}: {
		torrent: components['schemas']['MovieTorrent'] | components['schemas']['RichSeasonTorrent'];
	} = $props();
	let label = $derived(torrent.usenet ? 'NZB-Download' : 'Torrent');
	let dialogOpen = $state(false);
	let importedState = $derived(torrent.imported);

	async function closeDialog() {
		dialogOpen = false;
	}
	async function saveTorrent() {
		const { error } = await client.PATCH('/api/v1/torrent/{torrent_id}/status', {
			params: {
				path: {
					torrent_id: torrent.torrent_id!
				},
				query: {
					imported: importedState
				}
			}
		});
		if (error) {
			toast.error('Download konnte nicht aktualisiert werden.');
			return;
		}
		await invalidateAll();
		await closeDialog();
	}
</script>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger aria-label={`${label} bearbeiten`} class={buttonVariants({ variant: 'secondary' })}>Bearbeiten</Dialog.Trigger>
	<Dialog.Content class="w-full max-w-[600px] rounded-lg p-6 shadow-lg">
		<Dialog.Header>
			<Dialog.Title class="mb-1 text-xl font-semibold">{label} bearbeiten</Dialog.Title>
			<Dialog.Description class="mb-4 text-sm">
				{label} bearbeiten "{torrent.torrent_title}".
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex gap-2">
			<Label for="imported-state">{label} {importedState ? 'ist' : 'ist nicht'} importiert.</Label>
			<Switch bind:checked={importedState} id="imported-state" />
		</div>
		<Dialog.Footer class="mt-8 flex justify-between gap-2">
			<Button onclick={() => closeDialog()} variant="secondary">Cancel</Button>
			<Button onclick={() => saveTorrent()}>Speichern</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
