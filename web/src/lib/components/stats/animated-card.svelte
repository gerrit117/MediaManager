<script lang="ts">
 import Card from '$lib/components/stats/card.svelte';
 let {title,footer,number}:{title:string;footer:string;number:number}=$props();
 let text=$derived(Number.isFinite(number)?String(number).padStart(3,'0'):'000');
</script>
<Card {title} {footer}><span>{text}</span></Card>
