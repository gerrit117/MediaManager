export function createTranslator(entries: [string,string][]) {
 const translations=Object.fromEntries(entries);
 const reverse=Object.fromEntries(entries.map(([en,de])=>[de,en]));
 const escape=(text:string)=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 function template(source:string,target:string){
  const names:string[]=[];
  const expression=source.split(/(\{\w+\})/).map(part=>{
   if(/^\{\w+\}$/.test(part)){names.push(part.slice(1,-1));return '([\\s\\S]*?)';}
   return escape(part);
  }).join('');
  return {regex:new RegExp('^'+expression+'$'),names,target};
 }
 const templates=entries.filter(([key])=>/\{\w+\}/.test(key)).map(([en,de])=>({de:template(en,de),en:template(de,en)}));
 return (language:'de'|'en',source:string):string=>{
  if(typeof source!=='string')return source==null?'':JSON.stringify(source);
  const canonical=reverse[source]??source;
  if(translations[canonical]!==undefined)return language==='de'?translations[canonical]:canonical;
  for(const pair of templates){const item=pair[language],match=source.match(item.regex);if(match){const values=Object.fromEntries(item.names.map((name,i)=>[name,match[i+1]]));return item.target.replace(/\{(\w+)\}/g,(_,name)=>values[name]??'');}}
  return source;
 };
}
