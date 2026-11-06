<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import type { WithElementRef, WithoutChildren } from 'bits-ui';
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let {
		ref = $bindable(null),
		class: className,
		...restProps
	}: WithoutChildren<WithElementRef<HTMLAttributes<HTMLSpanElement>>> = $props();
</script>

<span
	bind:this={ref}
	aria-hidden="true"
	class={cn('flex size-9 items-center justify-center', className)}
	{...restProps}
>
	<Ellipsis class="size-4" />
	<span class="sr-only">{mmT($mmLocale, "More pages" )}</span>
</span>
