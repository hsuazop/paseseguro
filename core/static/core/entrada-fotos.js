(() => {
  'use strict';
  const input = document.getElementById('id_fotos');
  if (!input || typeof DataTransfer === 'undefined') return;
  // Keep the native multiple-file picker available on unsupported browsers.
  try { input.files = new DataTransfer().files; } catch (_) { return; }
  const camera = document.getElementById('camara-entrada');
  const preview = document.getElementById('vista-fotos');
  const error = document.getElementById('error-fotos');
  const counter = document.getElementById('contador-fotos');
  let photos = [];
  let urls = [];
  function render() {
    const transfer = new DataTransfer();
    photos.forEach(file => transfer.items.add(file));
    input.files = transfer.files;
    urls.forEach(url => URL.revokeObjectURL(url));
    urls = [];
    preview.replaceChildren();
    photos.forEach((file, index) => {
      const column = document.createElement('div');
      column.className = 'col-6 col-md-4';
      const card = document.createElement('div');
      card.className = 'card p-2 h-100';
      const img = document.createElement('img');
      const url = URL.createObjectURL(file);
      urls.push(url);
      img.src = url;
      img.alt = `Foto ${index + 1}`;
      img.style.cssText = 'width:100%;height:150px;object-fit:contain';
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'btn btn-sm btn-outline-danger mt-2';
      remove.textContent = `Quitar foto ${index + 1}`;
      remove.addEventListener('click', () => { photos.splice(index, 1); error.textContent = ''; render(); });
      card.append(img, remove);
      column.append(card);
      preview.append(column);
    });
    counter.textContent = `${photos.length} de 8 fotos seleccionadas`;
  }
  function add(files) {
    error.textContent = '';
    const incoming = Array.from(files);
    if (photos.length + incoming.length > 8) {
      error.textContent = 'Puedes adjuntar hasta 8 fotos. Quita alguna antes de agregar más.';
    } else if (incoming.some(file => file.size > 8 * 1024 * 1024)) {
      error.textContent = 'Cada foto debe pesar como máximo 8 MB.';
    } else if (incoming.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type))) {
      error.textContent = 'Usa fotos JPG, PNG o WEBP.';
    } else {
      photos.push(...incoming);
    }
    render();
  }
  document.querySelector('[data-photo-buttons]').hidden = false;
  document.getElementById('selector-fotos-nativo').hidden = true;
  document.getElementById('tomar-foto').addEventListener('click', () => camera.click());
  document.getElementById('elegir-fotos').addEventListener('click', () => input.click());
  camera.addEventListener('change', () => { add(camera.files); camera.value = ''; });
  input.addEventListener('change', () => add(input.files));
  input.form.addEventListener('submit', event => {
    if (!input.files.length) {
      event.preventDefault();
      error.textContent = 'Adjunta al menos una foto de la entrada.';
      document.getElementById('tomar-foto').focus();
    }
  });
  input.form.addEventListener('reset', () => { photos = []; error.textContent = ''; render(); });
  render();
})();
