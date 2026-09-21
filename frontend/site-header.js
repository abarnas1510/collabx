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
    const legacyNavigation = [...document.querySelectorAll('.main-nav-inner > a, .nav-list > a')]
      .map(link => ({ label: link.textContent.trim(), href: link.getAttribute('href') }))
      .filter(link => link.label && link.href && !['login', 'register'].includes(link.label.toLowerCase()));
    const pageNavigation = legacyNavigation.length ? legacyNavigation : navigation.map(([label, href]) => ({ label, href }));
    document.querySelectorAll('.utility-bar, .quick-banner, .main-header, .main-nav, .topbar, .top, body > .tricolor, img[src*="Emblem_of_India"], img[alt*="Emblem"]').forEach(element => element.remove());

    const isHome = currentPage() === 'index.html';
    const isProfile = currentPage() === 'profile.html';
    const isWorkspace = currentPage() === 'workspace.html';
    const homeAuthFallback = '';
    const profileAuth = isProfile ? '<a id="dashboard-link" class="collabx-login" href="index.html">Dashboard</a><button id="logout-btn" class="collabx-signout" type="button">Logout</button>' : '';
    const workspaceRole = isWorkspace ? '<span class="pill" id="workspace-role-pill">Role</span>' : '';
    const header = document.createElement('header');
    header.className = 'collabx-header';
    header.innerHTML = `
      <div class="collabx-header-inner">
        <a class="collabx-brand" href="index.html" aria-label="CollabX home">
          <img src="assets/collabx-logo.svg" alt="CollabX logo">
          <span><strong>COLLAB<span>X</span></strong><small>Digital Platform for Societal Innovation</small></span>
        </a>
        <button class="collabx-menu-button" type="button" aria-expanded="false" aria-controls="collabx-nav">Menu</button>
        <nav class="collabx-nav" id="collabx-nav" aria-label="Primary navigation">
          ${pageNavigation.map(({ label, href }) => `<a href="${href}"${currentPage() === href ? ' class="active"' : ''}>${label}</a>`).join('')}
          <span class="collabx-actions">${isProfile ? profileAuth : `<span id="nav-auth">${homeAuthFallback}</span>${isHome ? '' : `<a class="collabx-login${currentPage() === 'login.html' ? ' active' : ''}" href="login.html">Login</a><a class="collabx-signup${currentPage() === 'register.html' ? ' active' : ''}" href="register.html">Register</a>`}`}${workspaceRole}${languageSelect()}</span>
        </nav>
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
  }

  const style = document.createElement('style');
  style.textContent = `
    .collabx-header { background:#fff; border-bottom:3px solid #0B3C5D; box-shadow:0 2px 8px rgba(8,43,68,.08); position:relative; z-index:20; }
    .collabx-header-inner { max-width:1280px; min-height:82px; margin:0 auto; padding:10px 20px; display:flex; align-items:center; gap:24px; }
    .collabx-brand { display:flex; align-items:center; gap:12px; color:#0B3C5D; text-decoration:none; min-width:260px; }
    .collabx-brand img { width:56px; height:56px; object-fit:contain; }
    .collabx-brand strong { display:block; font:700 23px/1 'Noto Serif',serif; letter-spacing:.7px; }
    .collabx-brand strong span { color:#FF9933; }
    .collabx-brand small { display:block; margin-top:5px; color:#687786; font:500 10px/1.2 'Noto Sans',sans-serif; letter-spacing:.35px; text-transform:uppercase; }
    .collabx-nav { display:flex; align-items:center; gap:3px; margin-left:auto; }
    .collabx-nav > a { padding:10px 12px; color:#0B3C5D; font-size:13px; font-weight:600; white-space:nowrap; border-radius:3px; }
    .collabx-nav > a:hover, .collabx-nav > a.active { background:#FF9933; color:#0B3C5D; text-decoration:none; }
    .collabx-actions { display:flex; align-items:center; gap:7px; margin-left:8px; }
    #nav-auth { display:flex; align-items:center; gap:7px; }
    #nav-auth:empty { display:none; }
    .collabx-actions a { padding:8px 12px; border-radius:3px; font-size:12px; font-weight:700; white-space:nowrap; }
    .collabx-login { border:1px solid #0B3C5D; color:#0B3C5D; }
    .collabx-signup { background:#0B3C5D; color:#fff; }
    .collabx-signout { border:1px solid #B8C5D1; background:#fff; color:#0B3C5D; padding:8px 12px; border-radius:3px; font:700 12px 'Noto Sans',sans-serif; cursor:pointer; }
    .collabx-demo { border:1px solid #0F4C81; background:#0F4C81; color:#fff; padding:8px 12px; border-radius:3px; font:700 12px 'Noto Sans',sans-serif; cursor:pointer; white-space:nowrap; }
    .collabx-language { display:flex; align-items:center; gap:5px; margin-left:5px; color:#687786; font-size:11px; font-weight:600; }
    .collabx-language select { background:#fff; color:#0B3C5D; border:1px solid #B8C5D1; border-radius:3px; padding:7px 8px; font:600 12px 'Noto Sans',sans-serif; }
    .collabx-menu-button { display:none; margin-left:auto; background:#0B3C5D; color:#fff; border:0; border-radius:3px; padding:9px 12px; font:600 12px 'Noto Sans',sans-serif; }
    @media (max-width:900px) { .collabx-header-inner { flex-wrap:wrap; gap:10px; } .collabx-brand { min-width:0; } .collabx-menu-button { display:block; } .collabx-nav { display:none; width:100%; flex-direction:column; align-items:stretch; margin-left:0; padding:5px 0 8px; } .collabx-nav.open { display:flex; } .collabx-nav > a { padding:10px 12px; } .collabx-actions { margin:5px 0 0; flex-wrap:wrap; } .collabx-language { margin-left:0; } }
    @media (max-width:480px) { .collabx-brand img { width:46px; height:46px; } .collabx-brand strong { font-size:19px; } .collabx-brand small { font-size:8px; } }
  `;
  document.head.appendChild(style);
  if (document.body) renderHeader();
  else document.addEventListener('DOMContentLoaded', renderHeader, { once: true });
})();
