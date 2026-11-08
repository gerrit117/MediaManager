<script lang="ts" module>
	import {
		Bell,
		CircleDollarSign,
		Clapperboard,
		Home,
		Info,
		LifeBuoy,
		Settings,
		TvIcon
	} from 'lucide-svelte';
	import { resolve } from '$app/paths';

	import { PUBLIC_VERSION } from '$env/static/public';

	const data = {
		navMain: [
			{
				title: 'Dashboard',
				url: resolve('/dashboard', {}),
				icon: Home,
				isActive: true
			},
			{
				title: 'TV',
				url: resolve('/dashboard/tv', {}),
				icon: TvIcon,
				isActive: true,
				items: [
                    {title: 'Discover', url: resolve('/dashboard/tv/discover', {})},
					{
						title: 'Add a show',
						url: resolve('/dashboard/tv/add-show', {})
					},
					{
						title: 'Downloads',
						url: resolve('/dashboard/tv/torrents', {})
					},
					{
						title: 'Requests',
						url: resolve('/dashboard/tv/requests', {})
					}
				]
			},
			{
				title: 'Movies',
				url: resolve('/dashboard/movies', {}),
				icon: Clapperboard,
				isActive: true,
				items: [
                    {title: 'Discover', url: resolve('/dashboard/movies/discover', {})},
					{
						title: 'Add a movie',
						url: resolve('/dashboard/movies/add-movie', {})
					},
					{
						title: 'Downloads',
						url: resolve('/dashboard/movies/torrents', {})
					},
					{
						title: 'Requests',
						url: resolve('/dashboard/movies/requests', {})
					}
				]
			}
		],
		navSecondary: [
			{
				title: 'Notifications',
				url: resolve('/dashboard/notifications', {}),
				icon: Bell
			},
			{
				title: 'Settings',
				url: resolve('/dashboard/settings', {}),
				icon: Settings
			},
			{
				title: 'Support',
				url: 'https://github.com/maxdorninger/MediaManager/issues',
				icon: LifeBuoy
			},
			{
				title: 'Donate',
				url: 'https://github.com/sponsors/maxdorninger',
				icon: CircleDollarSign
			},
			{
				title: 'About',
				url: resolve('/dashboard/about', {}),
				icon: Info
			}
		]
	};
</script>

<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import NavMain from '$lib/components/nav/nav-main.svelte';
	import NavSecondary from '$lib/components/nav/nav-secondary.svelte';
	import NavUser from '$lib/components/nav/nav-user.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import {getContext} from 'svelte';
    const currentUser=getContext<()=>any>('user');
    let mainItems=$derived(data.navMain.map(item=>({...item,title:item.title==='Dashboard'?'Overview':item.title,items:item.items?.filter(sub=>currentUser?.()?.is_superuser||sub.title!=='Downloads').map(sub=>({...sub,title:!currentUser?.()?.is_superuser&&sub.title==='Add a show'?'Request series':!currentUser?.()?.is_superuser&&sub.title==='Add a movie'?'Request movie':sub.title}))})));
	import type { ComponentProps } from 'svelte';
	import logo from '$lib/images/logo.svg';

	const sidebar = Sidebar.useSidebar();
	afterNavigate(() => { if (sidebar.isMobile) sidebar.setOpenMobile(false); });
	let { ref = $bindable(null), ...restProps }: ComponentProps<typeof Sidebar.Root> = $props();
</script>

<Sidebar.Root {...restProps} bind:ref variant="inset">
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props })}
						<a href={resolve('/dashboard', {})} {...props}>
							<img class="size-12" src={logo} alt="Media Manager Logo" />
							<div class="grid flex-1 text-left text-sm leading-tight">
								<span class="truncate font-semibold">Media Manager</span>
								<span class="truncate text-xs">{PUBLIC_VERSION}</span>
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>
	<Sidebar.Content>
		<NavMain items={mainItems} />
		<!--  <NavProjects projects={data.projects}/> -->
		<NavSecondary class="mt-auto" items={data.navSecondary} />
	</Sidebar.Content>
	<Sidebar.Footer>
		<NavUser />
	</Sidebar.Footer>
</Sidebar.Root>
