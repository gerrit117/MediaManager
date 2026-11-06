<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { cn } from '$lib/utils.js';
	import Loader2Icon from '@lucide/svelte/icons/loader-2';
	import type { ComponentProps } from 'svelte';
	let { class: className, ...restProps }: ComponentProps<typeof Loader2Icon> = $props();
</script>

<Loader2Icon
	role="status"
	aria-label={mmT($mmLocale, "Loading")}
	class={cn('size-4 animate-spin', className)}
	{...restProps}
/>
