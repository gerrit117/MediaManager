export function createTranslator(entries: [string,string][]) {
 const translations=Object.fromEntries(entries);
 const reverse=Object.fromEntries(entries.map(([en,de])=>[de,en]));
 return (language:'de'|'en',source:string):string=>{
  const canonical=reverse[source]??source;
  return language==='de'?(translations[canonical]??source):canonical;
 };
}
