<script lang="ts">
	import { onMount } from 'svelte';
	import { env } from '$env/dynamic/public';
	import * as Card from '$lib/components/ui/card/index.js';

	type Indexer = {
		provider: string;
		indexer_id: string;
		name: string;
		categories: { id: number; name: string }[];
		selection: { movie_categories: number[]; tv_categories: number[] };
		error: string | null;
	};
	let indexers: Indexer[] = $state([]);
	let message = $state('Loading categories…');
	let busy = $state(false);

	async function load() {
		busy = true;
		try {
			const response = await fetch(`${env.PUBLIC_API_URL ?? ''}/api/v1/indexers/categories`, {
				credentials: 'include'
			});
			if (!response.ok) throw new Error('Could not load indexer categories.');
			indexers = await response.json();
			message = indexers.length
				? ''
				: 'Save a direct indexer connection or configure Prowlarr or Jackett to select categories.';
		} catch (error) {
			message = error instanceof Error ? error.message : 'Could not load categories.';
		} finally {
			busy = false;
		}
	}

	async function save(indexer: Indexer) {
		busy = true;
		try {
			const response = await fetch(
				`${env.PUBLIC_API_URL ?? ''}/api/v1/indexers/categories/${indexer.provider}/${encodeURIComponent(indexer.indexer_id)}`,
				{
					method: 'PUT',
					credentials: 'include',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(indexer.selection)
				}
			);
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Could not save category selection.');
			}
			indexer.selection = await response.json();
			message = `Saved categories for ${indexer.name}.`;
		} catch (error) {
			message = error instanceof Error ? error.message : 'Could not save categories.';
		} finally {
			busy = false;
		}
	}

	onMount(load);
</script>

<Card.Root id="indexer-categories">
	<Card.Header>
		<Card.Title>Indexer categories</Card.Title>
		<Card.Description>
			Choose movie and TV categories from each indexer's advertised categories. An empty selection
			keeps the provider's default search behavior.
		</Card.Description>
	</Card.Header>
	<Card.Content class="space-y-5">
		<button type="button" onclick={load} disabled={busy} class="rounded-md border px-4 py-2">
			Refresh categories
		</button>
		<p role="status">{message}</p>
		{#each indexers as indexer (`${indexer.provider}:${indexer.indexer_id}`)}
			<section class="space-y-3 rounded-lg border p-4">
				<h3 class="font-semibold">{indexer.name} · {indexer.provider}</h3>
				{#if indexer.error}
					<p role="alert">{indexer.error} Saved selections are retained.</p>
				{:else}
					<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
						<label class="flex min-w-0 flex-col gap-2">
							<span>Movie categories</span>
							<select
								multiple
								size="8"
								bind:value={indexer.selection.movie_categories}
								disabled={busy}
								class="w-full rounded-md border bg-background p-2"
							>
								{#each indexer.categories as category}
									<option value={category.id}>{category.name} ({category.id})</option>
								{/each}
							</select>
						</label>
						<label class="flex min-w-0 flex-col gap-2">
							<span>TV categories</span>
							<select
								multiple
								size="8"
								bind:value={indexer.selection.tv_categories}
								disabled={busy}
								class="w-full rounded-md border bg-background p-2"
							>
								{#each indexer.categories as category}
									<option value={category.id}>{category.name} ({category.id})</option>
								{/each}
							</select>
						</label>
					</div>
					<button
						type="button"
						onclick={() => save(indexer)}
						disabled={busy}
						class="rounded-md border px-4 py-2">Save categories</button
					>
				{/if}
			</section>
		{/each}
	</Card.Content>
</Card.Root>
