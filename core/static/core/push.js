(() => {
 'use strict';
 const panel=document.querySelector('[data-push-panel]');
 if(!panel) return;
 const status=panel.querySelector('[data-push-status]'),button=panel.querySelector('[data-push-enable]');
 const csrf=panel.querySelector('[name=csrfmiddlewaretoken]').value;
 const api=async(url,data)=>{
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(data),credentials:'same-origin',redirect:'error'});
  if(!r.ok) throw Error('No se pudo registrar el dispositivo. Intenta nuevamente.');
 };
 const supported='serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window && window.isSecureContext;
 if(!supported){status.textContent='Este navegador no permite push. Usa Chrome actualizado en Android y conexión HTTPS.';button.disabled=true;}
 const bind=async(ask)=>{
  const r=await fetch('/push/config/',{cache:'no-store',redirect:'error'});const config=await r.json();
  if(!config.configured) throw Error('El servidor todavía no tiene configurado el envío push. La bandeja SOS sí está disponible.');
  if(ask && await Notification.requestPermission()!=='granted') throw Error('Permiso no concedido. Puedes habilitarlo en la configuración del navegador o de Android.');
  if(Notification.permission!=='granted') return;
  await navigator.serviceWorker.register('/service-worker.js',{scope:'/'});
  const reg=await navigator.serviceWorker.ready;
  let sub=await reg.pushManager.getSubscription();
  if(!sub && !ask) return;
  if(!sub){const encoded=config.publicKey.replace(/-/g,'+').replace(/_/g,'/'); const bytes=Uint8Array.from(atob(encoded+'='.repeat((4-encoded.length%4)%4)),c=>c.charCodeAt(0));sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});}
  await api('/push/suscribir/',sub.toJSON());
  status.textContent='Notificaciones habilitadas para esta sesión. Revisa sonido y vibración en Android.';
 };
 button.addEventListener('click',async()=>{button.disabled=true;try{await bind(true)}catch(e){status.textContent=e.message}finally{button.disabled=false}});
 panel.querySelector('[data-push-disable]').addEventListener('click',async()=>{
  try{await api('/push/desactivar/',{});const reg=await navigator.serviceWorker.getRegistration('/');const sub=await reg?.pushManager.getSubscription();await sub?.unsubscribe();reg?.active?.postMessage({type:'clear-sos'});status.textContent='Notificaciones desactivadas en este dispositivo.';}catch(e){status.textContent=e.message}
 });
 if(supported && Notification.permission==='granted') bind(false).catch(e=>status.textContent=e.message);
 let seen=new Set();
 const refresh=async()=>{
  if(document.hidden)return;
  try{
   const r=await fetch('/guardia/sos/?format=json',{cache:'no-store',redirect:'error'});if(!r.ok)return;
   const {alertas}=await r.json();const list=panel.querySelector('[data-sos-live]');list.replaceChildren();
   for(const alert of alertas){const link=document.createElement('a');link.className='btn btn-outline-danger m-1';link.href=`/guardia/sos/${alert.id}/`;link.textContent=`${alert.estado==='NUEVA'?'SOS':'Atendiendo'} · ${alert.nombre} · Casa ${alert.casa}`;list.append(link);}
   if(alertas.some(a=>a.estado==='NUEVA'&&!seen.has(a.id))) navigator.vibrate?.([500,200,500]);
   seen=new Set(alertas.map(a=>a.id));
  }catch(_){}
 };
 refresh();setInterval(refresh,10000);document.addEventListener('visibilitychange',refresh);
 navigator.serviceWorker?.addEventListener('message',refresh);
 document.querySelectorAll('form[action$="/logout/"]').forEach(form=>form.addEventListener('submit',()=>navigator.serviceWorker?.controller?.postMessage({type:'clear-sos'})));
})();
