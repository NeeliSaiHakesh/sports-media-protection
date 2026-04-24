/**
 * theme.js — Chrome-style System / Light / Dark theme management
 * Runs immediately to prevent flash, then attaches toggle button.
 */

const THEMES = ['system', 'dark', 'light'];

const ICONS = {
  system: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  light:  `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  dark:   `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
};

const LABELS = {
  system: 'Theme: System',
  light:  'Theme: Light',
  dark:   'Theme: Dark',
};

function getStored() {
  try { return localStorage.getItem('gs-theme') || 'dark'; } catch { return 'dark'; }
}

function applyTheme(pref) {
  let resolved = pref;
  if (pref === 'system') {
    resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', resolved);
}

function updateBtn(btn, pref) {
  if (!btn) return;
  btn.innerHTML = ICONS[pref] || ICONS.system;
  btn.title = LABELS[pref] || 'Toggle theme';
  btn.setAttribute('aria-label', LABELS[pref] || 'Toggle theme');
}

// ── Run immediately to avoid flash ────────────────────────
applyTheme(getStored());

// ── System preference change listener ─────────────────────
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (getStored() === 'system') applyTheme('system');
});

// ── Attach button after DOM ready ─────────────────────────
(function attachToggle() {
  function init() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const pref = getStored();
    updateBtn(btn, pref);
    btn.addEventListener('click', () => {
      const current = getStored();
      const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
      try { localStorage.setItem('gs-theme', next); } catch {}
      applyTheme(next);
      updateBtn(btn, next);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
