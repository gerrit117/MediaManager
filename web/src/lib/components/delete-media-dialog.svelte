<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import type { components } from '$lib/api/api.ts';
	import { toast } from 'svelte-sonner';
	import client from '$lib/api/index.ts';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { getFullyQualifiedMediaName } from '$lib/utils.ts';
	import * as AlertDialog from '$lib/components/ui/alert-dialog/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { buttonVariants } from '$lib/components/ui/button/index.js';

	let {
		media,
		isShow
	}: {
		media: components['schemas']['PublicMovie'] | components['schemas']['PublicShow'];
		isShow: boolean;
	} = $props();
	let deleteDialogOpen = $state(false);
	let deleteFilesOnDisk = $state(false);
	let deleteTorrents = $state(false);

	async function delete_movie() {
		if (!media.id) {
			toast.error(mmT($mmLocale,'Movie ID is missing'));
			return;
		}
		const { error } = await client.DELETE('/api/v1/movies/{movie_id}', {
			params: {
				path: { movie_id: media.id },
				query: { delete_files_on_disk: deleteFilesOnDisk, delete_torrents: deleteTorrents }
			}
		});
		if (error) {
			toast.error(mmT($mmLocale,'Failed to delete movie: ' + error.detail));
		} else {
			toast.success(mmT($mmLocale,'Movie deleted successfully.'));
			deleteDialogOpen = false;
			await goto(resolve('/dashboard/movies', {}), { invalidateAll: true });
		}
	}

	async function delete_show() {
		const { error } = await client.DELETE('/api/v1/tv/shows/{show_id}', {
			params: {
				path: { show_id: media.id! },
				query: { delete_files_on_disk: deleteFilesOnDisk, delete_torrents: deleteTorrents }
			}
		});
		if (error) {
			toast.error(mmT($mmLocale,'Failed to delete show: ' + error.detail));
		} else {
			toast.success(mmT($mmLocale,'Show deleted successfully.'));
			deleteDialogOpen = false;
			await goto(resolve('/dashboard/tv', {}), { invalidateAll: true });
		}
	}
</script>

<AlertDialog.Root bind:open={deleteDialogOpen}>
	<AlertDialog.Trigger class={buttonVariants({ variant: 'destructive' })}>
		{mmT($mmLocale, isShow ? "Delete series" : "Delete movie")}
	</AlertDialog.Trigger>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title>{mmT($mmLocale, "Delete -" )} {getFullyQualifiedMediaName(media)}?</AlertDialog.Title>
			<AlertDialog.Description>
				{mmT($mmLocale, "This action cannot be undone. This will permanently delete" )}
				<strong>{getFullyQualifiedMediaName(media)}</strong>.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<div class="flex flex-col gap-3 py-4">
			<div class="flex items-center space-x-2">
				<Checkbox bind:checked={deleteFilesOnDisk} id="delete-files" />
				<Label
					for="delete-files"
					class="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
				>
					{mmT($mmLocale, "Also delete files on disk (this will only remove imported files, not downloads)" )}
				</Label>
			</div>
			<div class="flex items-center space-x-2">
				<Checkbox bind:checked={deleteTorrents} id="delete-torrents" />
				<Label
					for="delete-torrents"
					class="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
				>
					{mmT($mmLocale, "Auch Downloads aus dem jeweiligen Downloadmanager entfernen (NZB und Torrent)" )}
				</Label>
			</div>
		</div>
		<AlertDialog.Footer>
			<AlertDialog.Cancel>{mmT($mmLocale, "Cancel" )}</AlertDialog.Cancel>
			<AlertDialog.Action
				onclick={() => {
					if (isShow) {
						delete_show();
					} else delete_movie();
				}}
				class={buttonVariants({ variant: 'destructive' })}
			>
				{mmT($mmLocale, "Delete" )}
			</AlertDialog.Action>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>
