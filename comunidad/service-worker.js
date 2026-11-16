'use strict';
// No caching of accounts, attachments or authenticated pages.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('push', event => {
  event.waitUntil((async () => {
    try {
      const id = event.data?.json()?.alerta;
      if (!Number.isSafeInteger(id)) return;
      const response = await fetch(`/guardia/sos/${id}/datos/`, {credentials:'same-origin',cache:'no-store',redirect:'error'});
      if (!response.ok) return;
      const data = await response.json();
      if (!data.active) return;
      await self.registration.showNotification(data.title, {
        body:data.body, tag:`sos-${id}`, renotify:true, requireInteraction:true,
        vibrate:[500,200,500,200,800], icon:'/static/core/brand/icon-192.png',
        data:{url:data.url}, actions:[{action:'abrir',title:'Ver emergencia'}]
      });
      for (const client of await self.clients.matchAll({type:'window'})) client.postMessage({type:'sos',id});
    } catch (_) {
      // No personal information is exposed without a fresh authorization check.
    }
  })());
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async()=>{
    const url = new URL(event.notification.data?.url || '/guardia/sos/',self.location.origin);
    if(url.origin!==self.location.origin) return;
    const windows = await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const win of windows) if(new URL(win.url).origin===url.origin) {await win.navigate(url.href);return win.focus();}
    return self.clients.openWindow(url.href);
  })());
});
self.addEventListener('message',event=>{
  if(event.data?.type==='clear-sos') event.waitUntil(self.registration.getNotifications().then(items=>items.forEach(n=>n.close())));
});
