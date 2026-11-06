<script lang="ts">
	import { ArrowDown, ArrowUp, LoaderCircle } from 'lucide-svelte';
	import * as Table from '$lib/components/ui/table';
	import { type Snippet } from 'svelte';
	import { emptyFacets, availableFacets, matchesFacets, facetLabels, type Facets } from '$lib/release-filters';

	let {
		torrentsPromise,
		columns,
		rowSnippet
	}: {
		torrentsPromise: Promise<any>;
		columns: { name: string; id: string }[];
		rowSnippet: Snippet<[any]>;
	} = $props();

	let selected = $state<Facets>(emptyFacets());
	function toggleFilter(group: keyof Facets, tag: string) { selected = { ...selected, [group]: selected[group].includes(tag) ? selected[group].filter(x => x !== tag) : [...selected[group], tag] }; }
	let sortBy = $state({ col: 'score', ascending: false });

	function getSortedColumnState(column: string | undefined): boolean | null {
		if (sortBy.col !== column) return null;
		return sortBy.ascending;
	}

	function toggleSort(column: string) {
		if (column === sortBy.col) {
			sortBy.ascending = !sortBy.ascending;
		} else {
			sortBy = { col: column, ascending: true };
		}
	}
	function sort(data: any[], column: string, ascending: boolean): any[] {
		let modifier = ascending ? 1 : -1;
		return [...data].sort((a, b) => {
			if (a[column] < b[column]) {
				return -1 * modifier;
			} else if (a[column] > b[column]) {
				return modifier;
			} else {
				return 0;
			}
		});
	}
</script>

<div class="mt-4 w-full min-w-0 items-center">
	{#await torrentsPromise}
		<div class="flex w-full max-w-sm items-center space-x-2">
			<LoaderCircle class="animate-spin" />
			<p>Releases werden geladen …</p>
		</div>
	{:then data}
		<h3 class="mb-2 text-lg font-semibold">Gefundene Releases:</h3>
		{#if data?.length}
   {@const options = availableFacets(data)}
   <div class="mb-4 space-y-3 rounded-lg border p-3" aria-label="Release-Schnellfilter">
    {#each Object.keys(options) as key}
     {@const group = key as keyof Facets}
     {#if options[group].length}
      <div class="flex flex-wrap items-center gap-2" role="group" aria-label={facetLabels[group]}>
       <span class="min-w-24 text-sm font-semibold">{facetLabels[group]}</span>
       {#each options[group] as tag}
        <button type="button" aria-pressed={selected[group].includes(tag)} class="rounded-full border px-3 py-1.5 text-sm transition-colors aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground" onclick={() => toggleFilter(group, tag)}>{tag}</button>
       {/each}
      </div>
     {/if}
    {/each}
    <div class="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
     <span aria-live="polite">{data.filter((row: any) => matchesFacets(row, selected)).length} von {data.length} Releases</span>
     <button type="button" class="underline" onclick={() => selected = emptyFacets()}>Filter zurücksetzen</button>
    </div>
    <p class="text-xs text-muted-foreground">Tags aus dem Release-Namen; keine verifizierten Dateiinformationen. Innerhalb einer Gruppe gilt „oder“, zwischen Gruppen „und“.</p>
   </div>
  {/if}
  <div class="max-w-full overflow-auto rounded-md border p-2">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Title</Table.Head>
						{#each columns as column (column.id)}
							<Table.Head onclick={() => toggleSort(column.id)} class="cursor-pointer">
								<div class="inline-flex items-center">
									{column.name}
									{#if getSortedColumnState(column.id) === true}
										<ArrowUp />
									{:else if getSortedColumnState(column.id) === false}
										<ArrowDown />
									{:else}
										<!-- Preserve layout (column width) when no sort is applied -->
										<ArrowUp class="invisible"></ArrowUp>
									{/if}
								</div>
							</Table.Head>
						{/each}
						<Table.Head class="text-right">Actions</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#if data}
						{@const sortedData = sort(data.filter((row: any) => matchesFacets(row, selected)), sortBy.col, sortBy.ascending)}
						{#each sortedData as torrent (torrent.id)}
							<Table.Row>
								{@render rowSnippet(torrent)}
							</Table.Row>
						{:else}
							<Table.Cell colspan={columns.length + 2}>
								<div class="font-light text-center w-full">Keine passenden Releases gefunden.</div>
							</Table.Cell>
						{/each}
					{:else}
						<Table.Cell colspan={columns.length + 2}>
							<div class="w-full text-center font-light">
								Start searching by clicking the search button!
							</div>
						</Table.Cell>
					{/if}
				</Table.Body>
			</Table.Root>
		</div>
	{:catch error}
		<div class="w-full text-center text-red-500">Releases konnten nicht geladen werden.</div>
		<div class="w-full text-center text-red-500">Error: {error.message}</div>
	{/await}
</div>
