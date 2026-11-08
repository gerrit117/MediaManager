<script lang="ts">
	import { buttonVariants } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import { type Snippet } from 'svelte';

	let {
		open = $bindable(),
		triggerText,
		title,
		description,
		children
	}: {
		open: boolean;
		triggerText: string;
		title: string;
		description: string;
		children: Snippet;
	} = $props();
</script>

<Dialog.Root bind:open>
	<Dialog.Trigger class={buttonVariants({ variant: 'default' })}>{triggerText}</Dialog.Trigger>
	<Dialog.Content class="max-h-[calc(100dvh-2rem)] w-[calc(100vw-1rem)] max-w-6xl min-w-0 overflow-x-hidden overflow-y-auto overscroll-contain p-4 sm:p-6">
		<Dialog.Header>
			<Dialog.Title>{title}</Dialog.Title>
			<Dialog.Description>
				{description}
			</Dialog.Description>
		</Dialog.Header>
		{@render children()}
	</Dialog.Content>
</Dialog.Root>
