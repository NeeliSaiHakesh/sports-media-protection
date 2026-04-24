/**
 * toast.js — Global toast notification system
 * Usage: showToast('Message', 'success' | 'error' | 'info' | 'warning', durationMs)
 * Include this via <script src="js/toast.js"></script> on any page
 */

(function () {
  // Ensure container exists
  function getContainer() {
    let c = document.getElementById('gs-toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'gs-toast-container';
      c.style.cssText = `
        position:fixed; bottom:24px; right:24px; z-index:9999;
        display:flex; flex-direction:column-reverse; gap:10px;
        pointer-events:none;
      `;
      document.body.appendChild(c);
    }
    return c;
  }

  const ICONS = {
    success: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
    error:   `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    info:    `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="1" fill="#3B82F6"/></svg>`,
    warning: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="1" fill="#F59E0B"/></svg>`,
  };

  const BORDER_COLORS = {
    success: '#10B981',
    error:   '#EF4444',
    info:    '#3B82F6',
    warning: '#F59E0B',
  };

  window.showToast = function (message, type = 'info', duration = 4000) {
    const container = getContainer();
    const toast = document.createElement('div');
    const borderColor = BORDER_COLORS[type] || BORDER_COLORS.info;
    const icon = ICONS[type] || ICONS.info;

    toast.style.cssText = `
      display:flex; align-items:center; gap:12px;
      background:var(--bg-card, #111827);
      border:1px solid var(--border, rgba(255,255,255,0.08));
      border-left:3px solid ${borderColor};
      border-radius:10px;
      padding:12px 16px;
      font-size:0.875rem;
      font-weight:500;
      color:var(--text-primary, #F9FAFB);
      box-shadow:0 8px 32px rgba(0,0,0,0.5);
      min-width:260px; max-width:380px;
      pointer-events:all;
      cursor:pointer;
      opacity:0;
      transform:translateX(24px);
      transition:opacity 0.3s ease, transform 0.3s ease;
      font-family:'Inter',system-ui,sans-serif;
    `;

    toast.innerHTML = `
      <span style="flex-shrink:0">${icon}</span>
      <span style="flex:1; line-height:1.4">${message}</span>
      <button onclick="this.parentElement.remove()" style="
        background:none; border:none; cursor:pointer; padding:2px;
        color:var(--text-muted,#6B7280); font-size:1rem; line-height:1;
        flex-shrink:0;
      ">×</button>
    `;

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
      });
    });

    // Auto dismiss
    const timer = setTimeout(() => dismissToast(toast), duration);
    toast.addEventListener('click', () => { clearTimeout(timer); dismissToast(toast); });
  };

  function dismissToast(toast) {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(24px)';
    setTimeout(() => toast.remove(), 300);
  }

  // Convenience shortcuts
  window.toastSuccess = (msg) => showToast(msg, 'success');
  window.toastError   = (msg) => showToast(msg, 'error');
  window.toastInfo    = (msg) => showToast(msg, 'info');
  window.toastWarning = (msg) => showToast(msg, 'warning');
})();
