<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Dialog as DialogPrimitive, type WithoutChildrenOrChild } from 'bits-ui';
	import X from '@lucide/svelte/icons/x';
	import type { Snippet } from 'svelte';
	import * as Dialog from './index.js';
	import { cn } from '$lib/utils.js';

	let {
		ref = $bindable(null),
		class: className,
		portalProps,
		children,
		...restProps
	}: WithoutChildrenOrChild<DialogPrimitive.ContentProps> & {
		portalProps?: DialogPrimitive.PortalProps;
		children: Snippet;
	} = $props();
</script>

<Dialog.Portal {...portalProps}>
	<Dialog.Overlay />
	<DialogPrimitive.Content
		bind:ref
		class={cn(
			'fixed top-[50%] left-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg rounded-xl mm-dialog-fade',
			className
		)}
		{...restProps}
	>
		{@render children?.()}
		<DialogPrimitive.Close
			class="absolute top-2 right-2 flex size-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none"
		>
			<X class="size-4" />
			<span class="sr-only">{mmT($mmLocale, "Close" )}</span>
		</DialogPrimitive.Close>
	</DialogPrimitive.Content>
</Dialog.Portal>

<style>
 :global(.mm-dialog-fade[data-state="open"]) { animation:mm-dialog-show 120ms ease-out; }
 :global(.mm-dialog-fade[data-state="closed"]) { animation:mm-dialog-hide 100ms ease-in; }
 @keyframes -global-mm-dialog-show { from { opacity:0; } to { opacity:1; } }
 @keyframes -global-mm-dialog-hide { from { opacity:1; } to { opacity:0; } }
 @media (prefers-reduced-motion:reduce) { :global(.mm-dialog-fade[data-state]) { animation-duration:1ms; } }
</style>
