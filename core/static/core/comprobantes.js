(() => {
  const modal = document.getElementById('vista-comprobante');
  if (!modal) return;
  const image = modal.querySelector('[data-preview-image]');
  const pdf = modal.querySelector('[data-preview-pdf]');
  modal.addEventListener('show.bs.modal', event => {
    const button = event.relatedTarget;
    const url = button?.dataset.previewUrl;
    if (!url) { event.preventDefault(); return; }
    const isImage = button.dataset.previewType === 'image';
    image.hidden = !isImage; pdf.hidden = isImage;
    (isImage ? image : pdf).src = url;
    modal.querySelector('[data-preview-link]').href = url;
  });
  modal.addEventListener('hidden.bs.modal', () => {
    image.removeAttribute('src'); pdf.removeAttribute('src');
  });
})();
