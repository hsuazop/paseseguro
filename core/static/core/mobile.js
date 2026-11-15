/* Progressive enhancements: forms and tables remain usable without JavaScript. */
(() => {
  'use strict';

  const serverErrors = document.querySelector('[data-form-errors]');
  if (serverErrors) {
    serverErrors.querySelectorAll('a[href^="#"]').forEach(link => {
      const field = document.getElementById(link.hash.slice(1));
      if (field) {
        field.classList.add('is-invalid');
        field.setAttribute('aria-invalid', 'true');
      }
    });
    serverErrors.focus();
  }

  document.querySelectorAll('form').forEach(form => {
    // Use one accessible summary, including on screens that opt out of native bubbles.
    form.noValidate = true;
    let summary;
    form.addEventListener('submit', event => {
      const invalid = Array.from(form.elements).filter(field => field.willValidate && !field.validity.valid);
      summary?.remove();
      if (!invalid.length) return;
      event.preventDefault();
      summary = document.createElement('div');
      summary.className = 'alert alert-danger form-error-summary';
      summary.setAttribute('role', 'alert');
      summary.tabIndex = -1;
      const title = document.createElement('strong');
      title.textContent = 'Revisa estos datos para continuar';
      const list = document.createElement('ul');
      list.className = 'mb-0 mt-2';
      invalid.forEach(field => {
        field.classList.add('is-invalid');
        field.setAttribute('aria-invalid', 'true');
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.className = 'alert-link';
        link.href = '#' + field.id;
        link.textContent = `${field.labels?.[0]?.textContent.trim() || field.name}: ${field.validationMessage}`;
        link.addEventListener('click', event => { event.preventDefault(); field.focus(); });
        item.append(link);
        list.append(item);
      });
      summary.append(title, list);
      form.prepend(summary);
      summary.focus();
    });
    form.addEventListener('input', event => {
      if (event.target.validity?.valid) {
        event.target.classList.remove('is-invalid');
        event.target.removeAttribute('aria-invalid');
      }
    });
  });

  document.querySelectorAll('.app-sidebar nav, .app-mobile-nav, .resident-bottom-nav').forEach(nav => {
    const current = window.location.pathname === '/' ? '/dashboard/' : window.location.pathname;
    const matches = Array.from(nav.querySelectorAll('a[href]')).filter(link => {
      const path = new URL(link.href).pathname;
      return path === current || (!link.hasAttribute('data-nav-exact') && current.startsWith(path));
    }).sort((a, b) => new URL(b.href).pathname.length - new URL(a.href).pathname.length);
    const link = matches[0];
    if (link) {
      link.classList.add('active');
      link.setAttribute('aria-current', new URL(link.href).pathname === current ? 'page' : 'location');
    }
  });

  const sidebar = document.getElementById('sidebar');
  const toggles = document.querySelectorAll('[data-bs-target="#sidebar"]:not([data-bs-dismiss])');
  if (sidebar) {
    sidebar.addEventListener('show.bs.offcanvas', () => toggles.forEach(toggle => toggle.setAttribute('aria-expanded', 'true')));
    sidebar.addEventListener('hide.bs.offcanvas', () => toggles.forEach(toggle => toggle.setAttribute('aria-expanded', 'false')));
  }

  document.querySelectorAll('main .table-responsive').forEach(region => {
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', 'Listado; desplaza horizontalmente si es necesario');
  });

  document.querySelectorAll('table[data-mobile-cards], main .table-responsive > table:not([data-mobile-scroll])').forEach(table => {
    const headers = Array.from(table.tHead?.rows[0]?.cells || []);
    const rows = Array.from(table.tBodies).flatMap(body => Array.from(body.rows));
    // Grouped headers and spanning data cells keep their horizontal table layout.
    if (!headers.length || table.tHead.rows.length !== 1 || headers.some(cell => cell.colSpan > 1) ||
        rows.some(row => Array.from(row.cells).some(cell => cell.rowSpan > 1) ||
          (row.cells.length !== headers.length && !(row.cells.length === 1 && row.cells[0].colSpan === headers.length)))) return;

    table.setAttribute('role', 'table');
    table.tHead.setAttribute('role', 'rowgroup');
    table.tHead.rows[0].setAttribute('role', 'row');
    headers.forEach(header => {
      header.scope = 'col';
      header.setAttribute('role', 'columnheader');
    });
    Array.from(table.tBodies).forEach(body => body.setAttribute('role', 'rowgroup'));
    rows.forEach(row => {
      row.setAttribute('role', 'row');
      if (row.cells.length === 1 && row.cells[0].colSpan > 1) row.classList.add('mobile-table-empty');
      Array.from(row.cells).forEach((cell, index) => {
        cell.setAttribute('role', 'cell');
        const label = headers[index]?.textContent.trim();
        if (label && !row.classList.contains('mobile-table-empty')) {
          const caption = document.createElement('span');
          caption.className = 'mobile-cell-label';
          caption.textContent = label;
          caption.setAttribute('aria-hidden', 'true');
          cell.prepend(caption);
        } else if (!row.classList.contains('mobile-table-empty')) {
          cell.classList.add('mobile-table-actions');
        }
      });
    });
    table.classList.add('mobile-table');
  });
})();
