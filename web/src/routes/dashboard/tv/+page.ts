import client from '$lib/api';
export const load=async({fetch})=>({tvShows:await client.GET('/api/v1/tv/shows',{fetch}).then(r=>r.data)});
