/* Filter each table independently without changing the period's financial totals. */
(() => {
  'use strict';
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');

  document.querySelectorAll('[data-table-filter]').forEach(filter => {
    const table = document.getElementById(filter.dataset.tableFilter);
    if (!table) return;
    const input = filter.querySelector('input[type="search"]');
    const rows = Array.from(table.querySelectorAll('[data-search-text]'), row => ({
      row, text: normalize(row.dataset.searchText),
    }));
    const empty = table.querySelector('[data-search-empty]');
    const count = filter.querySelector('[data-search-count]');
    function search() {
      const query = normalize(input.value).trim().replace(/\s+/g, ' ');
      let visible = 0;
      rows.forEach(({ row, text }) => {
        const matches = text.includes(query);
        row.classList.toggle('d-none', !matches);
        if (matches) visible += 1;
      });
      empty?.classList.toggle('d-none', visible > 0);
      count.textContent = `${visible} de ${rows.length} registros`;
    }
    input.addEventListener('input', search);
    filter.querySelector('[data-clear-search]').addEventListener('click', () => {
      input.value = '';
      search();
      input.focus();
    });
    filter.hidden = false;
    search();
  });
})();
