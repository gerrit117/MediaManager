<script lang="ts">
	import {locale as mmLocale,t as mmT} from '$lib/i18n';
 import { onMount } from 'svelte';
 import { invalidateAll } from '$app/navigation';
 type Account={id:string;email:string;is_active:boolean;is_verified:boolean;is_superuser:boolean};
 let {users}:{users:Account[]}=$props();
 let creating=$state(false);
 let policies=$state<Record<string,any>>({});let filter=$state('');let selected=$state<Account|null>(null);
 let limit=$state<number|undefined>(10);let unlimited=$state(true);let automatic=$state(false);let password=$state('');let busy=$state(false);let message=$state('');let failed=$state(false);
 async function load(){try{const r=await fetch('/api/v1/users/request-policies');if(!r.ok)throw Error('Kontingente konnten nicht geladen werden.');policies=Object.fromEntries((await r.json()).map((x:any)=>[x.id,x]));}catch(e){failed=true;message=(e as Error).message;}}
 onMount(load);
 function create(){creating=true;selected={id:'',email:'',is_active:true,is_verified:true,is_superuser:false};unlimited=true;limit=10;automatic=false;password='';message='';}
 function edit(user:Account){creating=false;selected={...user};const p=policies[user.id];unlimited=p?.monthly_request_limit==null;limit=p?.monthly_request_limit??10;automatic=p?.auto_approve_requests??false;password='';message='';}
 async function save(e:SubmitEvent){e.preventDefault();if(!selected)return;busy=true;failed=false;message='';
  try{
   if(creating){
    const response=await fetch('/api/v1/users/admin-create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...selected,password,monthly_request_limit:unlimited?null:limit,auto_approve_requests:automatic})});
    const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Could not create user.');
    selected=null;creating=false;password='';message='User created.';await invalidateAll();await load();return;
   }
   const p=await fetch('/api/v1/users/'+selected.id+'/request-policy',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({monthly_request_limit:unlimited?null:limit,auto_approve_requests:automatic})});if(!p.ok)throw Error((await p.json()).detail??'Kontingent konnte nicht gespeichert werden.');
   const r=await fetch('/api/v1/users/'+selected.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:selected.email,is_active:selected.is_active,is_verified:selected.is_verified,is_superuser:selected.is_superuser,...(password?{password}: {})})});
   if(!r.ok)throw Error('Kontingent gespeichert, Kontodaten konnten nicht gespeichert werden. Bitte prüfen.');
   selected=null;password='';message='Benutzer gespeichert.';await invalidateAll();await load();
  }catch(e){failed=true;message=(e as Error).message;}finally{busy=false;}
 }
 async function remove(user:Account){if(!confirm(mmT($mmLocale,'Delete account')+' '+user.email+'?'))return;busy=true;
  try{const r=await fetch('/api/v1/users/'+user.id,{method:'DELETE'});if(!r.ok)throw Error('Löschen fehlgeschlagen.');await invalidateAll();await load();}catch(e){message=(e as Error).message;failed=true;}finally{busy=false;}
 }
</script>
<div class="space-y-4">
 <div class="flex justify-end"><button type="button" class="rounded-lg bg-primary px-4 py-2 text-primary-foreground" onclick={create} disabled={busy}>{mmT($mmLocale,'Add user')}</button></div>
 <p class="text-sm text-muted-foreground">{mmT($mmLocale, "Zwei Rollen: Admin verwaltet den Server. User können suchen und anfragen. Ein Film oder eine Staffel zählt als eine Anfrage. Das gemeinsame Kontingent erneuert sich zum Monatsbeginn in Europe/Berlin; Löschen gibt kein Kontingent zurück." )}</p>
 <label class="block text-sm">{mmT($mmLocale, "Benutzer suchen" )}<input class="mt-2 w-full rounded-md border bg-background p-3" bind:value={filter} type="search" /></label>
 {#if message}<p role="status" class:text-destructive={failed}>{mmT($mmLocale, message)}</p>{/if}
 <div class="grid gap-3 lg:grid-cols-2">
 {#each users.filter(u=>u.email.toLowerCase().includes(filter.toLowerCase())) as user (user.id)}
  {@const policy=policies[user.id]}
  <article class="min-w-0 rounded-xl border bg-background p-4">
   <div class="flex flex-wrap items-center justify-between gap-2"><strong class="break-all">{user.email}</strong><span class="rounded-full border px-3 py-1 text-xs">{user.is_superuser?mmT($mmLocale, "Admin"):mmT($mmLocale, "User")}</span></div>
   <p class="mt-2 text-sm text-muted-foreground">{user.is_active?mmT($mmLocale, "Aktiv"):mmT($mmLocale, "Deaktiviert")} · {user.is_verified?mmT($mmLocale, "Bestätigt"):mmT($mmLocale, "Unbestätigt")}</p>
   <p class="mt-3 font-medium">{policy?policy.used:'…'} / {user.is_superuser||policy?.monthly_request_limit==null?mmT($mmLocale, "unbegrenzt"):policy.monthly_request_limit} {mmT($mmLocale, "Anfragen diesen Monat" )}</p>
   <p class="mt-1 text-sm">{mmT($mmLocale, "Genehmigung:" )} {user.is_superuser||policy?.auto_approve_requests?mmT($mmLocale, "automatisch"):mmT($mmLocale, "manuell")}</p>
   <div class="mt-4 flex flex-wrap gap-2"><button class="rounded-md border px-3 py-2" type="button" onclick={()=>edit(user)} disabled={busy||!policy}>{mmT($mmLocale, "Profil bearbeiten" )}</button><button class="rounded-md border px-3 py-2 text-destructive" type="button" onclick={()=>remove(user)} disabled={busy}>{mmT($mmLocale, "Konto löschen" )}</button></div>
  </article>
 {:else}<p>{mmT($mmLocale, "Keine weiteren Benutzer gefunden. Dein eigenes Konto bearbeitest du oben im Bereich Account." )}</p>{/each}
 </div>
 {#if selected}
 <div role="dialog" aria-modal="true" aria-label={mmT($mmLocale,creating?"Add user":"Account profile")} class="fixed inset-0 z-50 grid place-items-center overflow-auto bg-black/70 p-4">
  <form onsubmit={save} class="max-h-[90vh] w-full max-w-xl space-y-4 overflow-auto rounded-xl border bg-card p-5 shadow-xl">
   <h3 class="text-xl font-semibold">{mmT($mmLocale,creating?"Add user":"Account profile")}</h3>
   <label class="block text-sm">{mmT($mmLocale, "E-Mail" )}<input type="email" required bind:value={selected.email} class="mt-1 w-full rounded-md border bg-background p-2"/></label>
   <label class="block text-sm">{mmT($mmLocale, "Rolle" )}<select bind:value={selected.is_superuser} class="mt-1 w-full rounded-md border bg-background p-2"><option value={false}>{mmT($mmLocale, "User" )}</option><option value={true}>{mmT($mmLocale, "Admin" )}</option></select></label>
   <div class="flex flex-wrap gap-4"><label><input type="checkbox" bind:checked={selected.is_active}/> {mmT($mmLocale, "Konto aktiv" )}</label><label><input type="checkbox" bind:checked={selected.is_verified}/> {mmT($mmLocale, "Konto bestätigt" )}</label></div>
   <fieldset disabled={selected.is_superuser} class="space-y-3 rounded-lg border p-3 disabled:opacity-50"><legend class="px-2 font-semibold">{mmT($mmLocale, "Anfragen" )}</legend>
    <label class="block"><input type="checkbox" bind:checked={unlimited}/> {mmT($mmLocale, "Unbegrenzte Anfragen" )}</label>
    {#if !unlimited}<label class="block text-sm">{mmT($mmLocale, "Anfragen pro Kalendermonat" )}<input aria-label={mmT($mmLocale, "Anfragen pro Kalendermonat")} type="number" min="0" max="100000" required bind:value={limit} class="mt-1 w-full rounded-md border bg-background p-2"/></label>{/if}
    <label class="block"><input type="checkbox" bind:checked={automatic}/> {mmT($mmLocale, "Automatische Genehmigung" )}</label>
   </fieldset>
   {#if selected.is_superuser}<p class="text-sm text-muted-foreground">{mmT($mmLocale, "Administratoren haben unbegrenzte, automatisch genehmigte Anfragen." )}</p>{/if}
   <label class="block text-sm">{mmT($mmLocale,creating?"Password (at least 12 characters)":"New password (leave empty to keep)")}<input required={creating} minlength={creating?12:undefined} type="password" autocomplete="new-password" bind:value={password} class="mt-1 w-full rounded-md border bg-background p-2"/></label>
   {#if message}<p role="alert">{mmT($mmLocale, message)}</p>{/if}
   <div class="flex flex-wrap justify-end gap-2"><button type="button" class="rounded-md border px-4 py-2" onclick={()=>{selected=null;password='';}} disabled={busy}>{mmT($mmLocale, "Abbrechen" )}</button><button type="submit" class="rounded-md bg-primary px-4 py-2 text-primary-foreground" disabled={busy}>{busy?mmT($mmLocale, "Speichert …"):mmT($mmLocale, "Speichern")}</button></div>
  </form>
 </div>
 {/if}
</div>
