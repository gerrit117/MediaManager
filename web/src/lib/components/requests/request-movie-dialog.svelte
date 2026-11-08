<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import RequestQuota from '$lib/components/request-quota.svelte';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Label } from '$lib/components/ui/label';
	import * as Select from '$lib/components/ui/select';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { getFullyQualifiedMediaName, getTorrentQualityString } from '$lib/utils.js';
	import { toast } from 'svelte-sonner';
	import client from '$lib/api';
	import type { components } from '$lib/api/api';
	import { invalidateAll } from '$app/navigation';

	let { movie }: { movie: components['schemas']['PublicMovie'] } = $props();
	let dialogOpen = $state(false);
	let minQuality = $state<string | undefined>(undefined);
	let wantedQuality = $state<string | undefined>(undefined);
	let isSubmittingRequest = $state(false);
	let submitRequestError = $state<string | null>(null);

	const qualityValues: components['schemas']['Quality'][] = [1, 2, 3, 4];
	let qualityOptions = $derived(
		qualityValues.map((q) => ({ value: q.toString(), label: getTorrentQualityString(q) }))
	);
	let isFormInvalid = $derived(
		!minQuality || !wantedQuality || parseInt(wantedQuality) > parseInt(minQuality)
	);

	async function handleRequestMovie() {
		isSubmittingRequest = true;
		submitRequestError = null;
		const { response, error } = await client.POST('/api/v1/movies/requests', {
			body: {
				movie_id: movie.id!,
				min_quality: parseInt(minQuality!) as components['schemas']['Quality'],
				wanted_quality: parseInt(wantedQuality!) as components['schemas']['Quality']
			}
		});
		isSubmittingRequest = false;

		if (response.ok) {
			dialogOpen = false;
			minQuality = undefined;
			wantedQuality = undefined;
			toast.success(mmT($mmLocale,'Movie request submitted successfully!'));
		} else {
			submitRequestError = (error as any)?.detail ?? 'Anfrage fehlgeschlagen';
			toast.error(mmT($mmLocale,submitRequestError??'Request failed'));
		}
		await invalidateAll();
	}
</script>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger
		class={buttonVariants({ variant: 'default' })}
		onclick={() => {
			dialogOpen = true;
		}}
	>
		{mmT($mmLocale, "Request Movie" )}
	</Dialog.Trigger>
	<Dialog.Content class="max-h-[90vh] w-fit min-w-[clamp(300px,50vw,600px)] overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{mmT($mmLocale, "Request" )} {getFullyQualifiedMediaName(movie)}</Dialog.Title>
			<Dialog.Description>{mmT($mmLocale, "Select desired qualities to submit a request." )}</Dialog.Description>
		</Dialog.Header>
		<div class="grid gap-4 py-4">
			<!-- Min Quality Select -->
			<div class="grid grid-cols-[1fr_3fr] items-center gap-4 md:grid-cols-[100px_1fr]">
				<Label class="text-right" for="min-quality">{mmT($mmLocale, "Min Quality" )}</Label>
				<Select.Root bind:value={minQuality} type="single">
					<Select.Trigger class="w-full" id="min-quality">
						{minQuality ? getTorrentQualityString(parseInt(minQuality)) : 'Select Minimum Quality'}
					</Select.Trigger>
					<Select.Content>
						{#each qualityOptions as option (option.value)}
							<Select.Item value={option.value}>{option.label}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

			<!-- Wanted Quality Select -->
			<div class="grid grid-cols-[1fr_3fr] items-center gap-4 md:grid-cols-[100px_1fr]">
				<Label class="text-right" for="wanted-quality">{mmT($mmLocale, "Wanted Quality" )}</Label>
				<Select.Root bind:value={wantedQuality} type="single">
					<Select.Trigger class="w-full" id="wanted-quality">
						{wantedQuality
							? getTorrentQualityString(parseInt(wantedQuality))
							: 'Select Wanted Quality'}
					</Select.Trigger>
					<Select.Content>
						{#each qualityOptions as option (option.value)}
							<Select.Item value={option.value}>{option.label}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

			{#if submitRequestError}
				<p class="col-span-full text-center text-sm text-red-500">{mmT($mmLocale, submitRequestError)}</p>
			{/if}
		</div>
		<RequestQuota />
		<Dialog.Footer>
			<Button disabled={isSubmittingRequest} onclick={() => (dialogOpen = false)} variant="outline"
				>{mmT($mmLocale, "Cancel" )}
			</Button>
			<Button disabled={isFormInvalid || isSubmittingRequest} onclick={handleRequestMovie}>
				{#if isSubmittingRequest}
					<LoaderCircle class="mr-2 h-4 w-4 animate-spin" />
					{mmT($mmLocale, "Submitting..." )}
				{:else}
					{mmT($mmLocale, "Submit Request" )}
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
