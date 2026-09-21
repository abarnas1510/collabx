(() => {
  const localHostnames = new Set(['localhost', '127.0.0.1', '[::1]']);
  const configuredApiUrl = window.__COLLABX_API_BASE__ || '';
  const localApiUrl = `http://${window.location.hostname}:8000`;
  const apiUrl = configuredApiUrl || (localHostnames.has(window.location.hostname) ? localApiUrl : '');

  if (!apiUrl) {
    console.error('CollabX API is not configured. Set the VITE_API_URL GitHub repository variable.');
  }

  window.COLLABX_API_BASE = apiUrl.replace(/\/$/, '');
})();
