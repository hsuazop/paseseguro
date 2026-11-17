const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = readFileSync('comunidad/service-worker.js', 'utf8');
async function push(payload, response) {
  const handlers = {}, shown = [];
  const self = {
    addEventListener: (name, fn) => handlers[name] = fn,
    registration: {showNotification: async (title, options) => shown.push({title, ...options})},
    clients: {matchAll: async () => []}
  };
  vm.runInNewContext(source, {self, URL, fetch: async () => {
    if (response instanceof Error) throw response;
    return response;
  }});
  let done;
  handlers.push({data: {json: () => payload}, waitUntil: p => done = p});
  await done;
  return shown;
}
(async () => {
  let shown = await push({alerta: 1}, {ok: true, json: async () => ({active:true, title:'SOS · Casa A1', body:'Residente · Residencial · Casa A1', url:'/guardia/sos/1/'})});
  assert.equal(shown[0].title, 'SOS · Casa A1');
  assert.equal(shown[0].vibrate.length, 5);
  assert.equal(shown[0].data.url, '/guardia/sos/1/');
  assert.equal((await push({alerta: 1}, {ok:false, status:403})).length, 0);
  assert.equal((await push({alerta: 1}, {ok:true, json:async () => ({active:false})})).length, 0);
  shown = await push({alerta: 1}, new Error('offline'));
  assert.equal(shown[0].tag, 'sos-conexion');
  assert.ok(!shown[0].body.includes('Residente'));
  assert.equal((await push({alerta: 1}, {ok:false, status:503}))[0].tag, 'sos-conexion');
  shown = await push({tipo:'prueba'});
  assert.equal(shown[0].tag, 'sos-prueba');
  assert.match(shown[0].body, /No es una emergencia/);
  console.log('PASS: SOS data, vibration, authorization, closed alert, offline fallback and isolated test.');
})().catch(error => {console.error(error); process.exitCode=1;});
