<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
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

	let page = $state(0);
	const pageSize = 10;
	$effect(() => { void torrentsPromise; void selected; void sortBy.col; void sortBy.ascending; page = 0; });
	let selected = $state<Facets>(emptyFacets());
	function toggleFilter(group: keyof Facets, tag: string) { selected = { ...selected, [group]: selected[group].includes(tag) ? selected[group].filter(x => x !== tag) : [...selected[group], tag] }; }
	let sortBy = $state({ col: '', ascending: false });

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
        if (!column) return data;
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
			<p>{mmT($mmLocale, "Releases werden geladen …" )}</p>
		</div>
	{:then data}
		<h3 class="mb-2 text-lg font-semibold">{mmT($mmLocale, "Gefundene Releases:" )}</h3>
		{#if data?.length}
   {@const options = availableFacets(data)}
   <details class="mb-4 rounded-lg border p-3" aria-label={mmT($mmLocale, "Release-Schnellfilter")}><summary class="min-h-8 cursor-pointer text-sm font-medium">{mmT($mmLocale,"Filters")} · {data.filter((row: any) => matchesFacets(row, selected)).length} / {data.length} {mmT($mmLocale,"Releases")}</summary><div class="mt-3 space-y-3">
    {#each Object.keys(options) as key}
     {@const group = key as keyof Facets}
     {#if options[group].length}
      <div class="flex flex-wrap items-center gap-2" role="group" aria-label={mmT($mmLocale, facetLabels[group])}>
       <span class="min-w-24 text-sm font-semibold">{mmT($mmLocale, facetLabels[group])}</span>
       {#each options[group] as tag}
        <button type="button" aria-pressed={selected[group].includes(tag)} class="rounded-full border px-3 py-1.5 text-sm transition-colors aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground" onclick={() => toggleFilter(group, tag)}>{mmT($mmLocale,tag)}</button>
       {/each}
      </div>
     {/if}
    {/each}
    <div class="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
     <span aria-live="polite">{data.filter((row: any) => matchesFacets(row, selected)).length} {mmT($mmLocale,"of")} {data.length} {mmT($mmLocale, "Releases" )}</span>
     <button type="button" class="underline" aria-pressed={!sortBy.col} onclick={() => sortBy = {col:'',ascending:false}}>{mmT($mmLocale,"Preferred release order")}</button>
     <button type="button" class="underline" onclick={() => selected = emptyFacets()}>{mmT($mmLocale, "Filter zurücksetzen" )}</button>
    </div>
    <p class="text-xs text-muted-foreground">{mmT($mmLocale, "Tags aus dem Release-Namen; keine verifizierten Dateiinformationen. Innerhalb einer Gruppe gilt „oder“, zwischen Gruppen „und“." )}</p>
   </div></details>
  {/if}
  {@const sortedData = sort((data ?? []).filter((row: any) => matchesFacets(row, selected)), sortBy.col, sortBy.ascending)}
  <label class="mb-3 flex items-center gap-2 text-sm md:hidden">{mmT($mmLocale,"Sort")}<select aria-label={mmT($mmLocale,"Sort")} class="min-h-11 min-w-0 flex-1 rounded-lg border bg-background px-3" value={sortBy.col} onchange={(event) => sortBy={col:event.currentTarget.value,ascending:true}}><option value="">{mmT($mmLocale,"Preferred release order")}</option>{#each columns as column}<option value={column.id}>{mmT($mmLocale,column.name)}</option>{/each}</select></label>
  <div class="release-results max-w-full rounded-md border p-2">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>{mmT($mmLocale, "Title" )}</Table.Head>
						{#each columns as column (column.id)}
							<Table.Head onclick={() => toggleSort(column.id)} class="cursor-pointer">
								<div class="inline-flex items-center">
									{mmT($mmLocale,column.name)}
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
						<Table.Head class="text-right">{mmT($mmLocale, "Actions" )}</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#if data}
						{#each sortedData.slice(page * pageSize, (page + 1) * pageSize) as torrent (torrent.id)}
							<Table.Row>
								{@render rowSnippet(torrent)}
							</Table.Row>
						{:else}
							<Table.Cell colspan={columns.length + 2}>
								<div class="font-light text-center w-full">{mmT($mmLocale, "Keine passenden Releases gefunden." )}</div>
							</Table.Cell>
						{/each}
					{:else}
						<Table.Cell colspan={columns.length + 2}>
							<div class="w-full text-center font-light">
								{mmT($mmLocale, "Start searching by clicking the search button!" )}
							</div>
						</Table.Cell>
					{/if}
				</Table.Body>
			</Table.Root>
		</div>
  {#if sortedData.length > pageSize}
   <nav class="mt-3 flex items-center justify-between gap-2" aria-label={mmT($mmLocale,'Release pages')}>
    <button class="min-h-11 rounded-lg border px-3 text-sm disabled:opacity-40" disabled={page===0} onclick={() => page--}>{mmT($mmLocale,'Previous')}</button>
    <span class="text-sm" aria-live="polite">{page+1} / {Math.ceil(sortedData.length/pageSize)}</span>
    <button class="min-h-11 rounded-lg border px-3 text-sm disabled:opacity-40" disabled={(page+1)*pageSize>=sortedData.length} onclick={() => page++}>{mmT($mmLocale,'Next')}</button>
   </nav>
  {/if}
	{:catch error}
		<div class="w-full text-center text-red-500">{mmT($mmLocale, "Releases konnten nicht geladen werden." )}</div>
		<div class="w-full text-center text-red-500">{mmT($mmLocale, "Error:" )} {error.message}</div>
	{/await}
</div>

<style>
 .release-results :global(td:first-child) { overflow-wrap:anywhere; white-space:normal; min-width:16rem; }
 @media (max-width:767px) {
  .release-results { border:0; padding:0; }
  .release-results :global(div:has(> table)) { overflow:visible; }
  .release-results :global(table), .release-results :global(tbody) { display:block; width:100%; }
  .release-results :global(thead) { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
  .release-results :global(tbody tr) { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px 12px; margin-bottom:12px; padding:14px; border:1px solid var(--border); border-radius:12px; background:var(--card); }
  .release-results :global(td) { display:block; min-width:0; padding:0; white-space:normal; overflow-wrap:anywhere; }
  .release-results :global(td:not(:first-child):not(:last-child))::before { content:attr(data-label); display:block; font-size:12px; color:var(--muted-foreground); margin-bottom:2px; }
  .release-results :global(td:first-child), .release-results :global(td:last-child), .release-results :global(td[colspan]) { grid-column:1/-1; min-width:0; }
  .release-results :global(td:first-child) { font-weight:600; line-height:1.5; padding-bottom:6px; }
  .release-results :global(td:last-child) { border-top:1px solid var(--border); padding-top:12px; }
  .release-results :global(td:last-child button) { min-height:44px; width:100%; }
 }
</style>
