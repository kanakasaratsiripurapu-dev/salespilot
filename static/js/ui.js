/**
 * SalesPilot UI module — sidebar interactions, forms, events.
 */
const UI = (() => {
  // DOM references
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  const searchInput = document.getElementById('search-input');
  const accountListEl = document.getElementById('account-list');
  const addForm = document.getElementById('add-account-form');
  const btnPickMap = document.getElementById('btn-pick-map');
  const btnOptimize = document.getElementById('btn-optimize');
  const btnRefresh = document.getElementById('btn-refresh');
  const btnSelectAll = document.getElementById('btn-select-all');
  const btnDeselectAll = document.getElementById('btn-deselect-all');
  const startAccountSelect = document.getElementById('start-account');
  const topNInput = document.getElementById('top-n');
  const routeResult = document.getElementById('route-result');
  const routeLoading = document.getElementById('route-loading');
  const routeDistance = document.getElementById('route-distance');
  const routeStops = document.getElementById('route-stops');
  const toastEl = document.getElementById('toast');

  let toastTimer;

  function initTabs() {
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
      });
    });
  }

  function toast(msg, type = 'info', duration = 3000) {
    clearTimeout(toastTimer);
    toastEl.textContent = msg;
    toastEl.className = `toast ${type}`;
    toastTimer = setTimeout(() => { toastEl.className = 'toast hidden'; }, duration);
  }

  function renderAccountList(accounts, selectedIds, startId, callbacks) {
    accountListEl.innerHTML = '';
    const query = searchInput.value.toLowerCase();

    accounts
      .filter(a => !query || a.account_name.toLowerCase().includes(query) || (a.industry || '').toLowerCase().includes(query))
      .forEach(a => {
        const li = document.createElement('li');
        li.className = 'account-item';

        const isSelected = selectedIds.has(a.account_id);
        const isStart = a.account_id === startId;

        li.innerHTML = `
          <input type="checkbox" data-id="${a.account_id}" ${isSelected ? 'checked' : ''} />
          <div class="account-info">
            <div class="account-name">${a.account_name}</div>
            <div class="account-meta">${a.industry || 'N/A'} &bull; $${(a.revenue || 0).toLocaleString()} &bull; ${a.region || '—'}</div>
          </div>
          ${isStart
            ? '<span class="start-badge">START</span>'
            : '<button class="set-start-btn" title="Set as start location">&#x25B6;</button>'}
        `;

        const checkbox = li.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', () => callbacks.onToggle(a.account_id, checkbox.checked));

        const startBtn = li.querySelector('.set-start-btn');
        if (startBtn) {
          startBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            callbacks.onSetStart(a.account_id);
          });
        }

        li.addEventListener('mouseenter', () => MapModule.highlightAccount(a.account_id, true));
        li.addEventListener('mouseleave', () => MapModule.highlightAccount(a.account_id, false));

        accountListEl.appendChild(li);
      });
  }

  function populateStartSelect(accounts, startId) {
    startAccountSelect.innerHTML = '<option value="">-- Choose start --</option>';
    accounts.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.account_id;
      opt.textContent = a.account_name;
      if (a.account_id === startId) opt.selected = true;
      startAccountSelect.appendChild(opt);
    });
  }

  function showRouteResult(totalKm, stops) {
    routeLoading.classList.add('hidden');
    routeResult.classList.remove('hidden');
    routeDistance.textContent = `Total distance: ${totalKm.toFixed(1)} km`;
    routeStops.innerHTML = '';
    stops.forEach(s => {
      const li = document.createElement('li');
      let cls = '';
      if (s.label === 'START') cls = 'stop-start';
      else if (s.label === 'END') cls = 'stop-end';
      li.className = cls;
      li.textContent = `${s.label}${s.label === 'ACCOUNT' ? ` ${s.stop_index}` : ''}: ${s.account_name || s.account_id}`;
      routeStops.appendChild(li);
    });
  }

  function showRouteLoading() {
    routeResult.classList.add('hidden');
    routeLoading.classList.remove('hidden');
  }

  function hideRouteLoading() {
    routeLoading.classList.add('hidden');
  }

  return {
    initTabs, toast, renderAccountList, populateStartSelect,
    showRouteResult, showRouteLoading, hideRouteLoading,
    // Expose elements for app.js to bind
    searchInput, addForm, btnPickMap, btnOptimize, btnRefresh,
    btnSelectAll, btnDeselectAll, startAccountSelect, topNInput,
  };
})();
