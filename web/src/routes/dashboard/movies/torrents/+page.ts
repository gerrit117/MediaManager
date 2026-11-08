import {redirect} from '@sveltejs/kit';
import {base} from '$app/paths';
import type { PageLoad } from './$types';
import client from '$lib/api';

export const load: PageLoad = async ({ fetch,parent }) => {
    const inherited=await parent();if(!inherited.user?.is_superuser)throw redirect(303,base+'/dashboard/movies/requests/');
	const { data } = await client.GET('/api/v1/movies/torrents', { fetch: fetch });

	return { torrents: data };
};
