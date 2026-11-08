<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import FilePathSuffixSelector from '$lib/components/download-dialogs/file-path-suffix-selector.svelte';
	import type { components } from '$lib/api/api';

	let {
		filePathSuffix = $bindable(),
		media,
		callback
	}: {
		filePathSuffix: string;
		media: components['schemas']['Movie'] | components['schemas']['Show'];
		callback: () => void;
	} = $props();
	let dialogOpen = $state(false);

	function onDownload() {
		callback();
		dialogOpen = false;
	}
</script>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger class={buttonVariants({class:"min-h-11 w-full"})}>{mmT($mmLocale, "Download" )}</Dialog.Trigger>
	<Dialog.Content class="w-[calc(100vw-2rem)] max-w-[600px] rounded-lg p-6 shadow-lg">
		<Dialog.Header>
			<Dialog.Title class="mb-1 text-xl font-semibold">{mmT($mmLocale, "Set File Path Suffix" )}</Dialog.Title>
			<Dialog.Description class="mb-4 text-sm">
				{mmT($mmLocale, "Set the filename suffix for the downloaded media files." )}
			</Dialog.Description>
		</Dialog.Header>
		<FilePathSuffixSelector bind:filePathSuffix {media} />
		<div class="mt-8 flex justify-between gap-2">
			<Button onclick={() => (dialogOpen = false)} variant="secondary">{mmT($mmLocale, "Cancel" )}</Button>
			<Button onclick={() => onDownload()}>{mmT($mmLocale, "An Downloadmanager senden" )}</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>
