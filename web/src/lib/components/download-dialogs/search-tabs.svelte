<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import * as Tabs from '$lib/components/ui/tabs';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { type Snippet } from 'svelte';

	let {
		tabState = $bindable(),
		isLoading,
		queryOverride = $bindable(),
		onSearch,
		basicModeContent,
		advancedModeHelpText
	}: {
		tabState: string;
		isLoading: boolean;
		queryOverride: string;
		onSearch: () => void;
		basicModeContent: Snippet;
		advancedModeHelpText: string;
	} = $props();
</script>

<Tabs.Root class="w-full" bind:value={tabState}>
	<Tabs.List>
		<Tabs.Trigger value="basic">{mmT($mmLocale, "Standard Mode" )}</Tabs.Trigger>
		<Tabs.Trigger value="advanced">{mmT($mmLocale, "Advanced Mode" )}</Tabs.Trigger>
	</Tabs.List>
	<Tabs.Content value="basic">
		<div class="grid w-full items-center gap-1.5">
			{@render basicModeContent()}
		</div>
	</Tabs.Content>
	<Tabs.Content value="advanced">
		<div class="grid w-full items-center gap-1.5">
			<Label for="query-override">{mmT($mmLocale, "Enter a custom query" )}</Label>
			<form class="flex w-full min-w-0 flex-col gap-2 sm:max-w-lg sm:flex-row" onsubmit={(event) => { event.preventDefault(); if (!isLoading) onSearch(); }}>
				<Input bind:value={queryOverride} id="query-override" type="text" />
				<Button type="submit" disabled={isLoading}>{mmT($mmLocale, "Indexer durchsuchen" )}</Button>
			</form>
			<p class="text-sm text-muted-foreground">
				{advancedModeHelpText}
			</p>
		</div>
	</Tabs.Content>
</Tabs.Root>
