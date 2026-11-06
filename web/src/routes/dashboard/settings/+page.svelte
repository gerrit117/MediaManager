<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
	import LanguageSelect from '$lib/components/language-select.svelte';
	import ConnectionSetup from '$lib/components/connection-setup.svelte';
	import SystemSettings from '$lib/components/system-settings.svelte';
	import IndexerServices from '$lib/components/indexer-services.svelte';
    import ReleaseRules from '$lib/components/release-rules.svelte';
    import LibraryManagement from '$lib/components/library-management.svelte';
	import {onMount} from 'svelte';

	import UserTable from '$lib/components/user-management.svelte';
	import RequestQuota from '$lib/components/request-quota.svelte';
	import { page } from '$app/state';
	import * as Card from '$lib/components/ui/card/index.js';
	import { getContext } from 'svelte';
	import UserSettings from '$lib/components/user-settings.svelte';
	import { Separator } from '$lib/components/ui/separator';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb/index.js';
	import { resolve } from '$app/paths';
	import type { components } from '$lib/api/api';

	let currentUser: () => components['schemas']['UserRead'] = getContext('user');
	let activeTab=$state('account');
	const tabs=[{id:'account',name:'Konto'},{id:'system',name:'System & Downloads'},{id:'indexers',name:'Indexer-Dienste'},{id:'library',name:'Library'},{id:'releases',name:'Release rules'},{id:'users',name:'Benutzerverwaltung'}];
	onMount(()=>{const section=new URLSearchParams(location.search).get('section');if(tabs.some(t=>t.id===section))activeTab=section!;const handler=(e:Event)=>{const target=(e as CustomEvent).detail;if(tabs.some(t=>t.id===target))activeTab=target;};window.addEventListener('mm-settings-tab',handler);return()=>window.removeEventListener('mm-settings-tab',handler);});
	let users: components['schemas']['UserRead'][] = $derived(
		(page.data.users ?? []).filter(
			(user: components['schemas']['UserRead']) => user.id !== currentUser().id
		)
	);
</script>

<svelte:head>
	<title>{mmT($mmLocale, "Settings - MediaManager" )}</title>
	<meta content="Manage your MediaManager settings and user preferences" name="description" />
</svelte:head>

<header class="flex h-16 shrink-0 items-center gap-2">
	<div class="flex items-center gap-2 px-4">
		<Sidebar.Trigger class="-ml-1" />
		<Separator class="mr-2 h-4" orientation="vertical" />
		<Breadcrumb.Root>
			<Breadcrumb.List>
				<Breadcrumb.Item class="hidden md:block">
					<Breadcrumb.Link href={resolve('/dashboard', {})}>MediaManager</Breadcrumb.Link>
				</Breadcrumb.Item>
				<Breadcrumb.Separator class="hidden md:block" />
				<Breadcrumb.Item>
					<Breadcrumb.Page>{mmT($mmLocale, "Settings" )}</Breadcrumb.Page>
				</Breadcrumb.Item>
			</Breadcrumb.List>
		</Breadcrumb.Root>
	</div>
</header>

<main class="mx-auto flex w-full min-w-0 flex-1 flex-col gap-4 p-4 md:max-w-[80em]">
 <div class="flex flex-wrap items-center justify-between gap-3"><h1 class="my-4 text-3xl font-bold">{mmT($mmLocale, "Settings" )}</h1><LanguageSelect/></div>
 <nav role="tablist" aria-label={mmT($mmLocale, "Settings sections")} class="sticky top-0 z-10 flex flex-wrap gap-2 rounded-xl border bg-background p-2 shadow-sm">
  {#each tabs.filter(t=>currentUser().is_superuser||t.id==='account') as tab}
   <button type="button" role="tab" aria-selected={activeTab===tab.id} aria-controls={'panel-'+tab.id} id={'tab-'+tab.id} class="rounded-lg px-4 py-2 text-sm font-medium aria-selected:bg-primary aria-selected:text-primary-foreground" onclick={()=>activeTab=tab.id}>{mmT($mmLocale, tab.name)}</button>
  {/each}
 </nav>
 <section role="tabpanel" id="panel-account" aria-labelledby="tab-account" hidden={activeTab!=='account'}>
  <Card.Root><Card.Header><Card.Title>{mmT($mmLocale, "My Account" )}</Card.Title><Card.Description>{mmT($mmLocale, "Change your email or password" )}</Card.Description></Card.Header><Card.Content class="space-y-4"><UserSettings/><RequestQuota/></Card.Content></Card.Root>
 </section>
 {#if currentUser().is_superuser}
  <section role="tabpanel" id="panel-system" aria-labelledby="tab-system" hidden={activeTab!=='system'}><ConnectionSetup/><SystemSettings/></section>
  <section role="tabpanel" id="panel-indexers" aria-labelledby="tab-indexers" hidden={activeTab!=='indexers'}><IndexerServices/></section>
  <section role="tabpanel" id="panel-library" aria-labelledby="tab-library" hidden={activeTab!=='library'}><LibraryManagement active={activeTab==='library'}/></section>
  <section role="tabpanel" id="panel-releases" aria-labelledby="tab-releases" hidden={activeTab!=='releases'}><ReleaseRules/></section>
  <section role="tabpanel" id="panel-users" aria-labelledby="tab-users" hidden={activeTab!=='users'}><Card.Root><Card.Header><Card.Title>{mmT($mmLocale, "Benutzerverwaltung" )}</Card.Title><Card.Description>{mmT($mmLocale, "Konten, Monatskontingente und automatische Genehmigung verwalten" )}</Card.Description></Card.Header><Card.Content><UserTable {users}/></Card.Content></Card.Root></section>
 {/if}
</main>
