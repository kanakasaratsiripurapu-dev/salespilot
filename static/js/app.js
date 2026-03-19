/**
 * SalesPilot App — state management and orchestration.
 */
(async function () {
  // ---- State ----
  let accounts = [];
  let selectedIds = new Set();
  let startId = null;
  let accountMap = {};  // id -> account object

  // ---- Init ----
  MapModule.init();
  UI.initTabs();

  await loadAccounts();

  // ---- Event bindings ----
  UI.searchInput.addEventListener('input', render);

  UI.btnRefresh.addEventListener('click', loadAccounts);

  UI.btnSelectAll.addEventListener('click', () => {
    accounts.forEach(a => selectedIds.add(a.account_id));
    render();
  });

  UI.btnDeselectAll.addEventListener('click', () => {
    selectedIds.clear();
    render();
  });

  UI.addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(UI.addForm);
    const data = {
      account_name: fd.get('account_name'),
      industry: fd.get('industry') || '',
      company_size: parseInt(fd.get('company_size')) || 0,
      revenue: parseFloat(fd.get('revenue')) || 0,
      region: fd.get('region') || '',
      deal_value: parseFloat(fd.get('deal_value')) || 0,
      sales_stage: fd.get('sales_stage'),
    };
    const lat = fd.get('latitude');
    const lon = fd.get('longitude');
    if (lat && lon) {
      data.latitude = parseFloat(lat);
      data.longitude = parseFloat(lon);
    }

    try {
      const acct = await API.createAccount(data);
      UI.toast(`Added "${acct.account_name}"`, 'success');
      UI.addForm.reset();
      MapModule.removePickMarker();
      await loadAccounts();
      // Switch to accounts tab
      document.querySelector('.tab[data-tab="accounts"]').click();
    } catch (err) {
      UI.toast(err.message, 'error');
    }
  });

  UI.btnPickMap.addEventListener('click', () => {
    UI.btnPickMap.classList.toggle('picking');
    if (UI.btnPickMap.classList.contains('picking')) {
      UI.toast('Click on the map to pick a location', 'info');
      MapModule.enablePickMode((lat, lng) => {
        UI.addForm.querySelector('[name="latitude"]').value = lat.toFixed(6);
        UI.addForm.querySelector('[name="longitude"]').value = lng.toFixed(6);
        UI.btnPickMap.classList.remove('picking');
        UI.toast(`Location set: ${lat.toFixed(4)}, ${lng.toFixed(4)}`, 'success');
      });
    } else {
      MapModule.disablePickMode();
    }
  });

  UI.startAccountSelect.addEventListener('change', () => {
    const val = UI.startAccountSelect.value;
    startId = val ? parseInt(val) : null;
    render();
  });

  UI.btnOptimize.addEventListener('click', async () => {
    if (!startId) {
      UI.toast('Select a start account first', 'error');
      return;
    }
    const ids = [...selectedIds];
    if (ids.length === 0) {
      UI.toast('Select at least one account to visit', 'error');
      return;
    }

    UI.showRouteLoading();
    MapModule.clearRoute();

    try {
      const res = await API.optimizeRoute({
        start_account_id: startId,
        account_ids: ids,
        top_n: parseInt(UI.topNInput.value) || 5,
        distance_mode: 'haversine',
      });

      // Enrich stops with account names
      const stops = res.route.map(s => ({
        ...s,
        account_name: accountMap[s.account_id]?.account_name || `Account ${s.account_id}`,
      }));

      UI.showRouteResult(res.total_distance_km, stops);
      MapModule.drawRoute(res.route, accountMap);
      UI.toast(`Route optimized! ${res.total_distance_km.toFixed(1)} km`, 'success');
    } catch (err) {
      UI.hideRouteLoading();
      UI.toast(err.message, 'error');
    }
  });

  // ---- Helpers ----
  async function loadAccounts() {
    try {
      const data = await API.getAccounts();
      accounts = data.accounts || [];
      accountMap = {};
      accounts.forEach(a => { accountMap[a.account_id] = a; });

      // Preserve selections that still exist
      const validIds = new Set(accounts.map(a => a.account_id));
      selectedIds = new Set([...selectedIds].filter(id => validIds.has(id)));
      if (startId && !validIds.has(startId)) startId = null;

      render();
      UI.toast(`Loaded ${accounts.length} accounts`, 'info');
    } catch (err) {
      UI.toast(`Failed to load accounts: ${err.message}`, 'error');
    }
  }

  function render() {
    UI.renderAccountList(accounts, selectedIds, startId, {
      onToggle(id, checked) {
        if (checked) selectedIds.add(id); else selectedIds.delete(id);
        render();
      },
      onSetStart(id) {
        startId = id;
        selectedIds.add(id);  // ensure start account is selected
        UI.toast(`Start set: ${accountMap[id]?.account_name}`, 'info');
        render();
      },
    });
    UI.populateStartSelect(accounts, startId);
    MapModule.plotAccounts(accounts, selectedIds, (id) => {
      // Toggle selection on map click
      if (selectedIds.has(id)) selectedIds.delete(id); else selectedIds.add(id);
      render();
    });
  }
})();
