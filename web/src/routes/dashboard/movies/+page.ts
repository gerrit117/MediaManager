import client from '$lib/api';
export const load=async({fetch})=>({movies:await client.GET('/api/v1/movies',{fetch}).then(r=>r.data)});
