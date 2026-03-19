/**
 * SalesPilot Map module — Leaflet map management.
 */
const MapModule = (() => {
  let map;
  let accountMarkers = {};  // account_id -> L.marker
  let routeLayer = null;
  let stopMarkers = [];
  let pickMode = false;
  let pickCallback = null;
  let pickMarker = null;

  function init() {
    map = L.map('map', { zoomControl: true }).setView([37.3, -121.5], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    map.on('click', (e) => {
      if (pickMode && pickCallback) {
        pickCallback(e.latlng.lat, e.latlng.lng);
        if (pickMarker) map.removeLayer(pickMarker);
        pickMarker = L.marker(e.latlng, {
          icon: L.divIcon({ className: 'numbered-marker', html: '?', iconSize: [28, 28], iconAnchor: [14, 14] }),
        }).addTo(map);
        disablePickMode();
      }
    });
  }

  function enablePickMode(cb) {
    pickMode = true;
    pickCallback = cb;
    map.getContainer().style.cursor = 'crosshair';
  }

  function disablePickMode() {
    pickMode = false;
    pickCallback = null;
    map.getContainer().style.cursor = '';
  }

  function clearAccountMarkers() {
    Object.values(accountMarkers).forEach(m => map.removeLayer(m));
    accountMarkers = {};
  }

  function plotAccounts(accounts, selectedIds, onClickAccount) {
    clearAccountMarkers();
    const bounds = [];
    accounts.forEach(a => {
      if (a.latitude == null || a.longitude == null) return;
      const isSelected = selectedIds.has(a.account_id);
      const marker = L.circleMarker([a.latitude, a.longitude], {
        radius: isSelected ? 7 : 5,
        fillColor: isSelected ? '#4fc3f7' : '#ff9800',
        color: '#fff',
        weight: 2,
        fillOpacity: 0.9,
      }).addTo(map);

      marker.bindPopup(`
        <strong>${a.account_name}</strong><br/>
        ${a.industry || 'N/A'} &bull; ${a.region || 'N/A'}<br/>
        Revenue: $${(a.revenue || 0).toLocaleString()}<br/>
        <small>ID: ${a.account_id}</small>
      `);

      if (onClickAccount) {
        marker.on('click', () => onClickAccount(a.account_id));
      }

      accountMarkers[a.account_id] = marker;
      bounds.push([a.latitude, a.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }

  function highlightAccount(accountId, highlight) {
    const m = accountMarkers[accountId];
    if (!m) return;
    m.setStyle({
      radius: highlight ? 7 : 5,
      fillColor: highlight ? '#4fc3f7' : '#ff9800',
    });
  }

  function clearRoute() {
    if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
    stopMarkers.forEach(m => map.removeLayer(m));
    stopMarkers = [];
  }

  function drawRoute(route, accountMap) {
    clearRoute();
    const latlngs = [];
    const bounds = [];

    route.forEach(stop => {
      const acct = accountMap[stop.account_id];
      if (!acct || acct.latitude == null) return;
      const ll = [acct.latitude, acct.longitude];
      latlngs.push(ll);
      bounds.push(ll);

      let cssClass = 'numbered-marker';
      let label = String(stop.stop_index + 1);
      if (stop.label === 'START') { cssClass += ' start'; label = 'S'; }
      else if (stop.label === 'END') { cssClass += ' end'; label = 'E'; }

      const marker = L.marker(ll, {
        icon: L.divIcon({
          className: cssClass,
          html: label,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
      }).addTo(map);

      marker.bindPopup(`
        <strong>${stop.label === 'START' ? 'START' : stop.label === 'END' ? 'END' : `Stop ${stop.stop_index}`}</strong><br/>
        ${acct.account_name}<br/>
        <small>ID: ${acct.account_id}</small>
      `);

      stopMarkers.push(marker);
    });

    if (latlngs.length >= 2) {
      routeLayer = L.polyline(latlngs, {
        color: '#4fc3f7',
        weight: 3,
        opacity: 0.8,
        dashArray: '8, 6',
      }).addTo(map);
    }

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [60, 60] });
    }
  }

  function removePickMarker() {
    if (pickMarker) { map.removeLayer(pickMarker); pickMarker = null; }
  }

  return { init, plotAccounts, highlightAccount, clearRoute, drawRoute, enablePickMode, disablePickMode, removePickMarker };
})();
