<script lang="ts">
 import {getContext} from 'svelte';
 import {invalidateAll} from '$app/navigation';
 import {locale,setLanguage,t,type Language} from '$lib/i18n';
 import type {components} from '$lib/api/api';
 const user=getContext<()=>components['schemas']['UserRead']>('user');
 let selector:HTMLSelectElement;
 let saving=$state(false),error=$state(''),saved=$state(false);
 async function change(language:Language,select?:HTMLSelectElement){
  error='';saved=false;saving=true;
  try{
   if(user?.()?.id){
    const response=await fetch('/api/v1/users/me',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferred_language:language})});
    if(!response.ok)throw Error('Language could not be saved. Please try again.');
   }
   setLanguage(language);saved=true;
   if(user?.()?.id)await invalidateAll().catch(()=>{});
  }catch{error='Language could not be saved. Please try again.';if(select)select.value=$locale;}
  finally{saving=false;}
 }
</script>
<div class="space-y-1">
 <label class="flex items-center gap-3 text-sm"><span>{t($locale,'Language')}</span><select bind:this={selector} aria-label={t($locale,'Language')} disabled={saving} value={$locale} onchange={(event)=>change(event.currentTarget.value as Language,event.currentTarget)} class="min-h-11 rounded-lg border bg-background px-3 py-2 text-base"><option value="de">Deutsch</option><option value="en">English</option></select></label>
 {#if user?.()?.id}{#if user().preferred_language==null&&!saved}<button type="button" disabled={saving} class="min-h-11 rounded-lg border px-3 text-sm" onclick={()=>change($locale,selector)}>{t($locale,'Save language in profile')}</button><p class="text-xs text-muted-foreground">{t($locale,'Your browser language is used until you save a profile preference.')}</p>{:else}<p class="text-xs text-muted-foreground">{t($locale,'Saved in your profile for all devices.')}</p>{/if}{/if}
 {#if saved&&user?.()?.id}<p role="status" class="text-xs text-muted-foreground">{t($locale,'Language saved.')}</p>{/if}
 {#if error}<p role="alert" class="text-xs text-destructive">{t($locale,error)}</p>{/if}
</div>
