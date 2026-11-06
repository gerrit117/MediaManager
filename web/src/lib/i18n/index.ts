import {writable} from 'svelte/store';
import strings from './strings.tsv?raw';
import {createTranslator} from './translate';
export type Language='de'|'en';
export const translations:Record<string,string>={};
for(const line of strings.trim().split('\n')){const [en,de]=line.split('\t');if(en&&de)translations[en]=de;}
const reverse=Object.fromEntries(Object.entries(translations).map(([en,de])=>[de,en]));
function initialLanguage():Language{
 if(typeof window==='undefined')return 'en';
 try{const stored=localStorage.getItem('mediamanager-language');if(stored==='de'||stored==='en')return stored;}catch{}
 return navigator.language.startsWith('de')?'de':'en';
}
export const locale=writable<Language>(initialLanguage());
export function setLanguage(language:Language){locale.set(language);if(typeof window!=='undefined'){try{localStorage.setItem('mediamanager-language',language);}catch{}document.documentElement.lang=language;document.cookie='mm_language='+language+';path=/;SameSite=Lax';}}
export const t=createTranslator(Object.entries(translations));
