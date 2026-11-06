<script lang="ts">
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import { Label } from '$lib/components/ui/label';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import client from '$lib/api';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { invalidateAll } from '$app/navigation';

	let { torrentId, torrentName, usenet = false }: { torrentId: string; torrentName: string; usenet?: boolean } = $props();
	let label = $derived(usenet ? 'NZB-Download' : 'Torrent');
	let dialogueState = $state(false);
	let deleteFiles = $state(false);

	async function deleteTorrent() {
		const { error } = await client.DELETE(`/api/v1/torrent/{torrent_id}`, {
			params: {
				path: {
					torrent_id: torrentId
				},
				query: {
					delete_files: deleteFiles
				}
			}
		});
		if (error) {
			toast.error(`Download konnte nicht gelöscht werden: ${error}`);
		} else {
			toast.success('Download gelöscht.');
			dialogueState = false;
		}
		await invalidateAll();
	}
</script>

<Dialog.Root bind:open={dialogueState}>
	<Dialog.Trigger aria-label={`${label} löschen`} class={buttonVariants({ variant: 'outline' }) + ' text-destructive hover:bg-destructive/10'}>Löschen</Dialog.Trigger>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>{label} löschen</Dialog.Title>
			<Dialog.Description>
				{label} löschen "{torrentName}". This action cannot be undone!
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex w-full max-w-sm items-center space-x-2">
			<Checkbox bind:checked={deleteFiles} id="delete-files" />
			<div class="flex flex-col">
				<Label for="delete-files">
					Delete associated files as well.
					<p class="text-sm font-normal text-muted-foreground">
						(Only files in the download location will be deleted)
					</p>
				</Label>
			</div>
		</div>

		<Dialog.Footer>
			<Button onclick={() => (dialogueState = false)}>Cancel</Button>
			<Button onclick={() => deleteTorrent()} variant="destructive">{label} löschen</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
