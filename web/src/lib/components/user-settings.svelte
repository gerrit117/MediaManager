<script lang="ts">
 import {passwordHint,validPassword} from '$lib/password-policy';
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import { Button } from '$lib/components/ui/button/index.js';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import client from '$lib/api';
	import { invalidateAll } from '$app/navigation';

	let newPassword: string = $state('');
	let newEmail: string = $state('');
	let dialogOpen = $state(false);

	async function saveUser() {
        if(newPassword&&!validPassword(newPassword)){toast.error(mmT($mmLocale,passwordHint));return;}
		const { error } = await client.PATCH('/api/v1/users/me', {
			body: {
				...(newPassword !== '' && { password: newPassword }),
				...(newEmail !== '' && { email: newEmail })
			}
		});
		if (error) {
			toast.error(mmT($mmLocale,`Failed to update user`));
		} else {
			toast.success(mmT($mmLocale,`Updated details successfully.`));
			dialogOpen = false;
		}
		newPassword = '';
		newEmail = '';
		await invalidateAll();
	}
</script>
<p class="my-2 text-xs text-muted-foreground">{mmT($mmLocale,passwordHint)}</p>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Trigger>
		<Button class="w-full" onclick={() => (dialogOpen = true)} variant="outline">
			{mmT($mmLocale, "Edit my details" )}
		</Button>
	</Dialog.Trigger>
	<Dialog.Content class="w-full max-w-[600px] rounded-lg p-6 shadow-lg">
		<Dialog.Header>
			<Dialog.Title class="mb-1 text-xl font-semibold">{mmT($mmLocale, "Edit User Details" )}</Dialog.Title>
			<Dialog.Description class="mb-4 text-sm">
				{mmT($mmLocale, "Change your email or password. Leave fields empty to not change them." )}
			</Dialog.Description>
		</Dialog.Header>
		<div class="space-y-6">
			<!-- Email -->
			<div>
				<Label class="mb-1 block text-sm font-medium" for="email">{mmT($mmLocale, "Email" )}</Label>
				<Input
					bind:value={newEmail}
					class="w-full"
					id="email"
					placeholder={mmT($mmLocale, "Keep empty to not change the email")}
					type="email"
				/>
			</div>
			<!-- Password -->
			<div>
				<Label class="mb-1 block text-sm font-medium" for="password">{mmT($mmLocale, "Password" )}</Label>
				<Input
					bind:value={newPassword}
					class="w-full"
					id="password"
					placeholder={mmT($mmLocale, "Keep empty to not change the password")}
					type="password" minlength={8}
				/>
			</div>
		</div>
		<div class="mt-8 flex justify-end gap-2">
			<Button onclick={() => saveUser()} variant="destructive">{mmT($mmLocale, "Save" )}</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>
