(() => {
  const productionApiUrl = 'https://collabx-uqwc.onrender.com';
  const configuredApiUrl = window.__COLLABX_API_BASE__ || window.COLLABX_API_BASE || productionApiUrl;
  const apiUrl = configuredApiUrl.replace(/\/$/, '');

  window.__COLLABX_API_BASE__ = apiUrl;
  window.COLLABX_API_BASE = apiUrl;
})();
