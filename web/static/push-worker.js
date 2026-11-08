/* Push only: never cache authenticated pages, media, API responses or credentials. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('push', event => {
 let data={};try{data=event.data?.json()??{};}catch{return;}
 event.waitUntil(self.registration.showNotification(data.title??'MediaManager',{body:data.body??'',icon:'/web/icon-192.png',badge:'/web/icon-192.png',tag:data.tag,data:{url:'/web/dashboard'}}));
});
self.addEventListener('notificationclick', event => {
 event.notification.close();
 event.waitUntil((async()=>{const url=new URL('/web/dashboard',self.location.origin).href;for(const client of await self.clients.matchAll({type:'window',includeUncontrolled:true})){if(new URL(client.url).origin===self.location.origin){await client.navigate(url);return client.focus();}}return self.clients.openWindow(url);})());
});
