(() => {
  const navigation = [
    ['Home', 'index.html'],
    ['Challenges', 'index.html#challenges'],
    ['Report a Problem', 'report.html']
  ];

  const languageOptions = [
    ['en', 'English'], ['hi', 'हिन्दी'], ['ta', 'தமிழ்'], ['te', 'తెలుగు'],
    ['bn', 'বাংলা'], ['mr', 'मराठी'], ['gu', 'ગુજરાતી'], ['kn', 'ಕನ್ನಡ'],
    ['ml', 'മലയാളം'], ['pa', 'ਪੰਜਾਬੀ'], ['or', 'ଓଡ଼ିଆ'], ['as', 'অসমীয়া'], ['ur', 'اردو']
  ];

  function currentPage() {
    return window.location.pathname.split('/').pop() || 'index.html';
  }

  function languageSelect() {
    const selected = localStorage.getItem('collabx_lang') || 'en';
    const id = currentPage() === 'workspace.html' ? 'workspace-lang' : 'globalLang';
    return `<label class="collabx-language"><span>Language</span><select id="${id}" aria-label="Language">${languageOptions.map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('')}</select></label>`;
  }

  function renderHeader() {
    document.querySelectorAll('.utility-bar, .quick-banner, .main-header, .main-nav, .topbar, .top, body > .tricolor').forEach(element => element.remove());

    const isHome = currentPage() === 'index.html';
    const isWorkspace = currentPage() === 'workspace.html';
    const storedUser = JSON.parse(localStorage.getItem('user') || 'null');
    const isAuthenticated = Boolean(localStorage.getItem('token') && storedUser);
    const routes = { citizen: 'citizen.html', university: 'university.html', industry: 'industry.html', govt: 'admin.html', admin: 'admin.html', expert: 'expert.html' };
    const dashboardHref = routes[storedUser && storedUser.role] || 'index.html';
    const authActions = `<a class="collabx-login${currentPage() === dashboardHref ? ' active' : ''}" href="${dashboardHref}">Dashboard</a><a class="collabx-login${currentPage() === 'profile.html' ? ' active' : ''}" href="profile.html">Profile</a><button id="logout-btn" class="collabx-signout" type="button">Logout</button>`;
    const publicActions = isHome ? '<button type="button" class="collabx-demo" onclick="openDemoModal()">⚡ Try Demo</button><a class="collabx-login" href="login.html">Login</a><a class="collabx-signup" href="register.html">Register</a>' : '';
    const workspaceRole = isWorkspace ? '<span class="pill" id="workspace-role-pill">Role</span>' : '';
    const header = document.createElement('header');
    header.className = 'collabx-header';
    header.innerHTML = `
      <div class="collabx-top-row">
        <a class="collabx-brand" href="index.html" aria-label="CollabX home">
          <img src="assets/collabx-logo.svg" alt="CollabX logo">
          <span><strong>COLLAB<span>X</span></strong><small>Digital Platform for Societal Innovation</small></span>
        </a>
        ${languageSelect()}
        <button class="collabx-menu-button" type="button" aria-expanded="false" aria-controls="collabx-nav">Menu</button>
      </div>
      <div class="collabx-nav-row">
        <nav class="collabx-nav" id="collabx-nav" aria-label="Primary navigation">
          <a href="index.html"${isHome ? ' class="active"' : ''}>Home</a>
          <a href="index.html#journey">How It Works</a>
          <a href="index.html#participate">Participate</a>
        </nav>
        <div class="collabx-actions" id="nav-auth">${isAuthenticated ? authActions : publicActions}${workspaceRole}</div>
      </div>`;

    document.body.prepend(header);
    const menuButton = header.querySelector('.collabx-menu-button');
    const nav = header.querySelector('.collabx-nav');
    menuButton.addEventListener('click', () => {
      const expanded = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!expanded));
      nav.classList.toggle('open', !expanded);
    });

    const language = header.querySelector('#globalLang, #workspace-lang');
    language.addEventListener('change', () => {
      if (typeof window.changeGlobalLang === 'function') window.changeGlobalLang(language.value);
      if (typeof window.changeWorkspaceLang === 'function') window.changeWorkspaceLang(language.value);
      localStorage.setItem('collabx_lang', language.value);
      window.dispatchEvent(new CustomEvent('collabx-language-changed'));
    });

    const logoutButton = header.querySelector('#logout-btn');
    if (logoutButton) logoutButton.addEventListener('click', () => {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = 'index.html';
    });
  }

  const style = document.createElement('style');
  style.textContent = `
    .collabx-header { position:relative; z-index:20; box-shadow:0 2px 8px rgba(8,43,68,.08); }
    .collabx-top-row { max-width:1280px; margin:0 auto; padding:0 20px; display:flex; align-items:center; }
    .collabx-nav-row { width:100%; padding:0 max(20px, calc((100% - 1280px) / 2 + 20px)); display:flex; align-items:center; }
    .collabx-top-row { min-height:82px; gap:24px; background:#fff; }
    .collabx-nav-row { min-height:48px; background:#0B3C5D; }
    .collabx-header::after { content:''; display:block; height:0; }
    .collabx-brand { display:flex; align-items:center; gap:12px; color:#0B3C5D; text-decoration:none; min-width:260px; }
    .collabx-brand img { width:56px; height:56px; object-fit:contain; }
    .collabx-brand strong { display:block; font:700 23px/1 'Noto Serif',serif; letter-spacing:.7px; }
    .collabx-brand strong span { color:#FF9933; }
    .collabx-brand small { display:block; margin-top:5px; color:#687786; font:500 10px/1.2 'Noto Sans',sans-serif; letter-spacing:.35px; text-transform:uppercase; }
    .collabx-nav { display:flex; align-items:center; gap:3px; }
    .collabx-nav > a { padding:10px 12px; color:#fff; font-size:13px; font-weight:600; white-space:nowrap; border-radius:3px; }
    .collabx-nav > a:hover, .collabx-nav > a.active { background:#FF9933; color:#0B3C5D; text-decoration:none; }
    .collabx-actions { display:flex; align-items:center; gap:7px; margin-left:auto; }
    #nav-auth { display:flex; align-items:center; gap:7px; }
    #nav-auth:empty { display:none; }
    .collabx-actions a { padding:8px 12px; border-radius:3px; font-size:12px; font-weight:700; white-space:nowrap; }
    .collabx-login { border:1px solid #0B3C5D; color:#0B3C5D; }
    .collabx-signup { background:#0B3C5D; color:#fff; }
    .collabx-signout { border:1px solid #B8C5D1; background:#fff; color:#0B3C5D; padding:8px 12px; border-radius:3px; font:700 12px 'Noto Sans',sans-serif; cursor:pointer; }
    .collabx-demo { border:1px solid #0F4C81; background:#0F4C81; color:#fff; padding:8px 12px; border-radius:3px; font:700 12px 'Noto Sans',sans-serif; cursor:pointer; white-space:nowrap; }
    .collabx-language { display:flex; align-items:center; gap:5px; margin-left:auto; color:#687786; font-size:11px; font-weight:600; }
    .collabx-language select { background:#fff; color:#0B3C5D; border:1px solid #B8C5D1; border-radius:3px; padding:7px 8px; font:600 12px 'Noto Sans',sans-serif; }
    .collabx-menu-button { display:none; margin-left:auto; background:#0B3C5D; color:#fff; border:0; border-radius:3px; padding:9px 12px; font:600 12px 'Noto Sans',sans-serif; }
    @media (max-width:900px) { .collabx-top-row { flex-wrap:wrap; gap:10px; } .collabx-brand { min-width:0; } .collabx-menu-button { display:block; } .collabx-nav-row { flex-wrap:wrap; padding-top:5px; padding-bottom:8px; } .collabx-nav { display:none; width:100%; flex-direction:column; align-items:stretch; } .collabx-nav.open { display:flex; } .collabx-nav > a { padding:10px 12px; } .collabx-actions { margin:5px 0 0; flex-wrap:wrap; } .collabx-language { margin-left:auto; } }
    @media (max-width:480px) { .collabx-brand img { width:46px; height:46px; } .collabx-brand strong { font-size:19px; } .collabx-brand small { font-size:8px; } }
  `;
  document.head.appendChild(style);
  if (document.body) renderHeader();
  else document.addEventListener('DOMContentLoaded', renderHeader, { once: true });
})();
