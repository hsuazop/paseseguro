/* Use Django's bundled Select2 assets, including its Spanish translation. */
(() => {
  'use strict';
  const $ = window.jQuery;
  if (!$?.fn.select2) return;

  function enhance(select) {
    // Django's autocomplete and two-column selectors already provide search.
    if (select.matches('.select2-hidden-accessible, .admin-autocomplete, .selectfilter, .selectfilterstacked') ||
        select.closest('.empty-form, .selector') || select.name.includes('__prefix__')) return;
    const $select = $(select);
    const parent = select.closest('.modal, .offcanvas');
    $select.select2({
      language: 'es',
      width: '100%',
      minimumResultsForSearch: 0,
      dropdownParent: parent ? $(parent) : $(document.body),
    });
    const container = $select.next('.select2-container')[0];
    container.classList.add('searchable-select');
    if (select.classList.contains('form-select-lg')) container.classList.add('searchable-select-lg');
    if (select.classList.contains('form-select-sm')) container.classList.add('searchable-select-sm');
    const selection = container.querySelector('.select2-selection');
    const label = select.labels?.[0]?.textContent.trim() || select.getAttribute('aria-label') || select.name;
    selection.setAttribute('aria-label', label);
    if (select.required) selection.setAttribute('aria-required', 'true');
    if (select.hasAttribute('aria-describedby')) selection.setAttribute('aria-describedby', select.getAttribute('aria-describedby'));

    $select.on('select2:open', () => {
      const search = (parent || document.body).querySelector('.select2-container--open .select2-search__field') ||
        container.querySelector('.select2-search__field');
      if (search) {
        search.placeholder = 'Buscar...';
        search.setAttribute('aria-label', 'Buscar opciones');
        search.focus();
      }
    });
    $select.on('select2:select select2:unselect', () => {
      // Select2 emits jQuery events. Notify existing native change listeners too.
      // Inline onchange already ran, so do not submit auto-filters twice.
      const inlineChange = select.onchange;
      select.onchange = null;
      try {
        select.dispatchEvent(new Event('change', { bubbles: true }));
        select.dispatchEvent(new Event('input', { bubbles: true }));
      } finally {
        select.onchange = inlineChange;
      }
    });
    select.addEventListener('invalid', event => {
      event.preventDefault();
      selection.focus();
      $select.select2('open');
    });
    // Error-summary links and labels can still focus the original select.
    select.addEventListener('focus', () => selection.focus());
  }

  function scan(root) {
    if (root.nodeType !== Node.ELEMENT_NODE && root !== document) return;
    if (root.matches?.('select')) enhance(root);
    root.querySelectorAll('select').forEach(enhance);
  }

  $(function () {
    scan(document);
    new MutationObserver(records => {
      records.forEach(record => record.addedNodes.forEach(scan));
    }).observe(document.body, { childList: true, subtree: true });
    document.addEventListener('reset', event => {
      setTimeout(() => $(event.target).find('select.select2-hidden-accessible').trigger('change.select2'), 0);
    });
  });
})();
