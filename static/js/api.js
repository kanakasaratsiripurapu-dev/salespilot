/**
 * SalesPilot API client.
 */
const API = (() => {
  const BASE = '';  // same origin

  async function _fetch(url, opts = {}) {
    const res = await fetch(BASE + url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  return {
    getAccounts()          { return _fetch('/v1/accounts'); },
    getAccount(id)         { return _fetch(`/v1/accounts/${id}`); },
    createAccount(data)    { return _fetch('/v1/accounts', { method: 'POST', body: JSON.stringify(data) }); },
    deleteAccount(id)      { return _fetch(`/v1/accounts/${id}`, { method: 'DELETE' }); },
    scoreAccounts(ids)     { return _fetch('/v1/score-accounts', { method: 'POST', body: JSON.stringify({ account_ids: ids }) }); },
    optimizeRoute(data)    { return _fetch('/v1/optimize-route', { method: 'POST', body: JSON.stringify(data) }); },
    loadData()             { return _fetch('/v1/load-data', { method: 'POST' }); },
    health()               { return _fetch('/health'); },
  };
})();
