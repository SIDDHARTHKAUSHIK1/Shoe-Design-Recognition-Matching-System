/**
 * ShoeMatch AI — Frontend Application Logic (Vanilla JavaScript)
 */

// ==========================================
// Native Server Base URL & API Helpers
// ==========================================
window.getApiBaseUrl = function() {
  try {
    const saved = localStorage.getItem("shoematch_api_base_url");
    if (saved && saved.trim()) {
      let url = saved.trim();
      return url.endsWith("/") ? url.slice(0, -1) : url;
    }
  } catch (e) {}

  // Capacitor Native Platform Resolution
  if (window.Capacitor && window.Capacitor.isNativePlatform()) {
    try {
      const mode = localStorage.getItem("shoematch_mobile_target");
      if (mode === "emulator") {
        return "http://10.0.2.2:8000";
      }
    } catch(e) {}
    // Default to local dev LAN IP for physical device over WiFi
    return "http://192.168.29.14:8000";
  }

  // Deployed configuration (frontend/config.js). Set when the API is hosted
  // on a different origin than the static UI. Empty = same-origin.
  if (window.SHOEMATCH_API_BASE) {
    const cfg = String(window.SHOEMATCH_API_BASE).trim();
    if (cfg) return cfg.endsWith("/") ? cfg.slice(0, -1) : cfg;
  }

  return "";
};

window.getApiUrl = function(path) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const base = window.getApiBaseUrl();
  const cleanPath = path.startsWith("/") ? path : "/" + path;
  return base ? base + cleanPath : cleanPath;
};

window.switchTab = function(tabId) {
  const navBtns = document.querySelectorAll(".nav-item[data-tab]");
  const tabPanes = document.querySelectorAll(".tab-pane");
  navBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tabId));
  tabPanes.forEach(pane => pane.classList.toggle("active", pane.id === tabId));
  if (tabId === "logs-tab" && window.fetchLogs) window.fetchLogs();
};

window.getImageUrl = function(path) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const base = window.getApiBaseUrl();
  const cleanPath = path.startsWith("/") ? path : "/" + path;
  return base ? base + cleanPath : cleanPath;
};

window._cachedAuthToken = null;

window.getAuthToken = function() {
  if (window._cachedAuthToken !== null) {
    return window._cachedAuthToken;
  }
  try {
    const local = localStorage.getItem("shoematch_auth_token") || "";
    window._cachedAuthToken = local;
    return local;
  } catch (e) {
    return "";
  }
};

window.setAuthToken = function(token) {
  window._cachedAuthToken = token || "";
  try {
    if (token) {
      localStorage.setItem("shoematch_auth_token", token);
    } else {
      localStorage.removeItem("shoematch_auth_token");
    }
  } catch (e) {}

  // Capacitor Native Preferences Storage
  try {
    if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Preferences) {
      const prefs = window.Capacitor.Plugins.Preferences;
      if (token) {
        prefs.set({ key: "shoematch_auth_token", value: token });
      } else {
        prefs.remove({ key: "shoematch_auth_token" });
      }
    }
  } catch (e) {
    console.warn("Capacitor preferences write warning:", e);
  }
};

// Async init token from Capacitor Preferences on native boot
(async function initNativeTokenStorage() {
  try {
    if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Preferences) {
      const prefs = window.Capacitor.Plugins.Preferences;
      const res = await prefs.get({ key: "shoematch_auth_token" });
      if (res && res.value) {
        window._cachedAuthToken = res.value;
        try { localStorage.setItem("shoematch_auth_token", res.value); } catch(e){}
      }
    }
  } catch (e) {
    console.warn("Capacitor preferences read warning:", e);
  }
})();

window.authenticatedFetch = async function(url, options = {}) {
  const token = window.getAuthToken();
  options.headers = options.headers || {};
  if (token && !options.headers["Authorization"]) {
    options.headers["Authorization"] = "Bearer " + token;
  }
  return fetch(url, options);
};

window.handleLoginSubmit = async function(e) {
  if (e) e.preventDefault();
  const usernameInput = document.getElementById("login-username");
  const passwordInput = document.getElementById("login-password");
  const alertEl = document.getElementById("login-error-alert");
  if (alertEl) alertEl.style.display = "none";

  let username = usernameInput ? usernameInput.value.trim() : "";
  let password = passwordInput ? passwordInput.value.trim() : "";

  // Dev testing convenience: auto-fill default passwords if blank
  if (username.toLowerCase() === "admin" && !password) {
    password = "admin123";
  } else if (username.toLowerCase() === "employee" && !password) {
    password = "emp123";
  }

  if (!username) {
    if (alertEl) {
      alertEl.textContent = "Please enter a username (e.g. admin or employee).";
      alertEl.style.display = "block";
    }
    return;
  }

  try {
    const res = await fetch(window.getApiUrl("/api/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) {
      if (alertEl) {
        alertEl.textContent = data.detail || "Authentication failed.";
        alertEl.style.display = "block";
      }
      return;
    }

    window.setAuthToken(data.token);
    window.updateUserUI(data.user);
    const loginModal = document.getElementById("login-modal");
    if (loginModal) loginModal.style.display = "none";
    if (window.showToast) window.showToast(`Welcome back, ${data.user.full_name}!`, "success");
    
    if (window.loadCatalog) window.loadCatalog();
  } catch (err) {
    console.error("Login error:", err);
    if (alertEl) {
      alertEl.textContent = "Network error connecting to auth server.";
      alertEl.style.display = "block";
    }
  }
};

window.switchTab = function(tabId) {
  const navBtns = document.querySelectorAll(".nav-item[data-tab]");
  const tabPanes = document.querySelectorAll(".tab-pane");
  navBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tabId));
  tabPanes.forEach(pane => pane.classList.toggle("active", pane.id === tabId));
  if (tabId === "logs-tab" && window.fetchLogs) window.fetchLogs();
};

window.handleLogout = async function() {
  try {
    await window.authenticatedFetch(window.getApiUrl("/api/auth/logout"), { method: "POST" });
  } catch (e) {}
  window.setAuthToken("");
  window.updateUserUI(null);
  const loginModal = document.getElementById("login-modal");
  if (loginModal) loginModal.style.display = "flex";
  if (window.showToast) window.showToast("Logged out successfully.", "info");
};

window.updateUserUI = function(user) {
  const nameEl = document.getElementById("user-display-name");
  const roleEl = document.getElementById("user-role-badge");
  const avatarEl = document.getElementById("user-avatar-initials");
  const loginModal = document.getElementById("login-modal");
  const pwdModal = document.getElementById("change-password-modal");
  const adminTabNav = document.getElementById("nav-admin");
  const locTabNav = document.getElementById("nav-locations");

  if (user) {
    if (nameEl) nameEl.textContent = user.full_name || user.username;
    if (roleEl) roleEl.textContent = user.role.toUpperCase();
    if (avatarEl) avatarEl.textContent = (user.full_name || user.username).charAt(0).toUpperCase();
    if (loginModal) loginModal.style.display = "none";
    if (adminTabNav) adminTabNav.style.display = (user.role === "admin") ? "flex" : "none";
    if (locTabNav) locTabNav.style.display = (user.role === "admin") ? "flex" : "none";

    // Ensure password reset modal is never displayed for testing
    if (pwdModal) pwdModal.style.display = "none";

    window.fetchDashboardStats();
    if (user.role === "admin") {
      window.fetchAdminUsers();
    }
  } else {
    if (nameEl) nameEl.textContent = "Guest";
    if (roleEl) roleEl.textContent = "EMPLOYEE";
    if (avatarEl) avatarEl.textContent = "G";
    if (loginModal) loginModal.style.display = "flex";
    if (pwdModal) pwdModal.style.display = "none";
    if (adminTabNav) adminTabNav.style.display = "none";
  }
};

window.handleChangePasswordSubmit = async function(e) {
  if (e) e.preventDefault();
  const oldPassword = document.getElementById("change-old-password")?.value.trim();
  const newPassword = document.getElementById("change-new-password")?.value.trim();
  const confirmPassword = document.getElementById("change-confirm-password")?.value.trim();
  const errEl = document.getElementById("change-password-error");

  if (errEl) errEl.style.display = "none";

  if (!oldPassword || !newPassword || !confirmPassword) {
    if (errEl) {
      errEl.textContent = "All fields are required.";
      errEl.style.display = "block";
    }
    return;
  }

  if (newPassword !== confirmPassword) {
    if (errEl) {
      errEl.textContent = "New password and confirmation do not match.";
      errEl.style.display = "block";
    }
    return;
  }

  if (newPassword === oldPassword) {
    if (errEl) {
      errEl.textContent = "New password cannot be the same as the default password.";
      errEl.style.display = "block";
    }
    return;
  }

  try {
    const res = await window.authenticatedFetch(window.getApiUrl("/api/auth/change-password"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) {
        errEl.textContent = data.detail || "Failed to update password.";
        errEl.style.display = "block";
      }
      return;
    }

    const pwdModal = document.getElementById("change-password-modal");
    if (pwdModal) pwdModal.style.display = "none";
    if (window.showToast) window.showToast("Password updated successfully!", "success");
    
    // Refresh auth session
    window.checkAuthSession();
  } catch (err) {
    if (errEl) {
      errEl.textContent = "Network error updating password.";
      errEl.style.display = "block";
    }
  }
};

window.fetchDashboardStats = async function() {
  try {
    const res = await window.authenticatedFetch(window.getApiUrl("/api/logs?limit=100"));
    const data = await res.json();
    const logs = data.logs || [];

    const searchesCountEl = document.getElementById("dash-searches-count");
    const accuracyPctEl = document.getElementById("dash-accuracy-pct");
    const avgLatencyEl = document.getElementById("dash-avg-latency");
    const recentLogsContainer = document.getElementById("dashboard-recent-logs-list");

    if (searchesCountEl) searchesCountEl.textContent = logs.length;
    
    if (logs.length > 0) {
      const highCount = logs.filter(l => (l.confidence_pct || 0) >= 85).length;
      const accPct = Math.round((highCount / logs.length) * 100);
      if (accuracyPctEl) accuracyPctEl.textContent = `${accPct}%`;

      const avgLat = Math.round(logs.reduce((acc, l) => acc + (l.latency_ms || 0), 0) / logs.length);
      if (avgLatencyEl) avgLatencyEl.textContent = `${avgLat} ms`;
    } else {
      if (accuracyPctEl) accuracyPctEl.textContent = "100%";
      if (avgLatencyEl) avgLatencyEl.textContent = "-- ms";
    }

    if (recentLogsContainer) {
      if (logs.length === 0) {
        recentLogsContainer.innerHTML = `<div style="padding: 14px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">No recent search activity logged yet.</div>`;
      } else {
        recentLogsContainer.innerHTML = logs.slice(0, 5).map(log => {
          const matchName = log.top_match_name || log.top_match_id || "Unmatched";
          const conf = log.confidence_pct ? `${log.confidence_pct}%` : "--%";
          const cat = log.detected_category || "shoe";
          const imgUrl = window.getLogThumbnailUrl ? window.getLogThumbnailUrl(log.query_image_path) : window.getImageUrl(log.query_image_path);
          const fallbackSvg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='1.5'><path d='M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z'/><path d='M16 8l-4 4'/></svg>";
          return `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-surface-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
              <div style="display: flex; align-items: center; gap: 12px;">
                <img src="${imgUrl}" style="width: 40px; height: 40px; object-fit: cover; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);" onerror="this.onerror=null; this.src='${fallbackSvg}';">
                <div>
                  <div style="font-size: 0.84rem; font-weight: 700; color: var(--text-primary);">${matchName}</div>
                  <div style="font-size: 0.72rem; color: var(--text-muted);">${log.created_at || 'Just now'} • <span style="text-transform: uppercase;">${cat}</span></div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <span class="preview-match-pill ${log.confidence_pct >= 85 ? 'high' : log.confidence_pct >= 70 ? 'moderate' : 'low'}">${conf} Match</span>
              </div>
            </div>
          `;
        }).join("");
      }
    }
  } catch (e) {
    console.warn("Could not fetch dashboard stats:", e);
  }
};

window.fetchAdminUsers = async function() {
  try {
    const res = await window.authenticatedFetch(window.getApiUrl("/api/admin/users"));
    if (!res.ok) return;
    const data = await res.json();
    const users = data.users || [];

    const countEl = document.getElementById("admin-stat-users-count");
    if (countEl) countEl.textContent = users.length;

    const tbody = document.getElementById("admin-users-tbody");
    if (tbody) {
      tbody.innerHTML = users.map(u => `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700;">#${u.user_id}</td>
          <td style="font-weight: 600; color: var(--text-primary);">${u.full_name}</td>
          <td style="font-family: var(--font-mono);">${u.username}</td>
          <td><span class="preview-match-pill ${u.role === 'admin' ? 'high' : 'moderate'}">${u.role.toUpperCase()}</span></td>
          <td><span style="color: ${u.is_active ? 'var(--status-success-text)' : 'var(--status-danger-text)'}; font-weight: 700;">${u.is_active ? 'Active' : 'Disabled'}</span></td>
          <td style="font-size: 0.75rem; color: var(--text-muted);">${u.last_login || 'Never'}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="window.toggleUserStatus(${u.user_id}, ${u.is_active})">
              ${u.is_active ? 'Deactivate' : 'Activate'}
            </button>
          </td>
        </tr>
      `).join("");
    }

    // Fetch admin stats summary
    const statsRes = await window.authenticatedFetch(window.getApiUrl("/api/admin/stats"));
    if (statsRes.ok) {
      const statsData = await statsRes.json();
      const activeDes = document.getElementById("admin-stat-active-designs");
      const archDes = document.getElementById("admin-stat-archived-designs");
      const totalQ = document.getElementById("admin-stat-total-queries");

      if (activeDes) activeDes.textContent = statsData.total_designs || 0;
      if (archDes) archDes.textContent = "0";
      if (totalQ) totalQ.textContent = statsData.total_queries || 0;
    }
  } catch (e) {
    console.warn("Could not fetch admin users:", e);
  }
};

window.openCreateUserModal = function() {
  const modal = document.getElementById("create-user-modal");
  const errEl = document.getElementById("create-user-error");
  if (errEl) errEl.style.display = "none";
  if (modal) modal.style.display = "flex";
};

window.closeCreateUserModal = function() {
  const modal = document.getElementById("create-user-modal");
  if (modal) modal.style.display = "none";
};

window.handleCreateUserSubmit = async function(e) {
  if (e) e.preventDefault();
  const fullName = document.getElementById("create-full-name")?.value.trim();
  const username = document.getElementById("create-username")?.value.trim();
  const password = document.getElementById("create-password")?.value.trim();
  const role = document.getElementById("create-role")?.value;
  const errEl = document.getElementById("create-user-error");

  if (errEl) errEl.style.display = "none";

  try {
    const res = await window.authenticatedFetch(window.getApiUrl("/api/admin/users"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: fullName, username, password, role })
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) {
        errEl.textContent = data.detail || "Failed to create user.";
        errEl.style.display = "block";
      }
      return;
    }
    window.closeCreateUserModal();
    if (window.showToast) window.showToast(`User '${username}' created successfully!`, "success");
    window.fetchAdminUsers();
  } catch (err) {
    if (errEl) {
      errEl.textContent = "Network error creating user account.";
      errEl.style.display = "block";
    }
  }
};

window.toggleUserStatus = async function(userId, currentStatus) {
  const newStatus = currentStatus ? 0 : 1;
  try {
    const res = await window.authenticatedFetch(window.getApiUrl(`/api/admin/users/${userId}`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: newStatus })
    });
    if (res.ok) {
      if (window.showToast) window.showToast(`User ID ${userId} status updated!`, "success");
      window.fetchAdminUsers();
    }
  } catch (e) {
    console.error("Error toggling user status:", e);
  }
};

window.checkAuthSession = async function() {
  const token = window.getAuthToken();
  if (!token) {
    window.updateUserUI(null);
    return;
  }
  try {
    const res = await window.authenticatedFetch(window.getApiUrl("/api/auth/me"));
    const data = await res.json();
    if (data.authenticated && data.user) {
      window.updateUserUI(data.user);
    } else {
      window.setAuthToken("");
      window.updateUserUI(null);
    }
  } catch (e) {
    window.updateUserUI(null);
  }
};

window.openServerSettingsModal = function() {
  const modal = document.getElementById("server-settings-modal");
  const input = document.getElementById("input-server-url");
  const alertEl = document.getElementById("server-status-alert");
  if (input) {
    input.value = window.getApiBaseUrl() || (window.location.origin.startsWith("http") ? window.location.origin : "http://localhost:8000");
  }
  if (alertEl) alertEl.style.display = "none";
  if (modal) modal.style.display = "flex";
};

window.closeServerSettingsModal = function() {
  const modal = document.getElementById("server-settings-modal");
  if (modal) modal.style.display = "none";
};

window.testServerConnection = async function() {
  const input = document.getElementById("input-server-url");
  const alertEl = document.getElementById("server-status-alert");
  if (!input || !alertEl) return;
  
  let targetUrl = input.value.trim();
  if (targetUrl.endsWith("/")) targetUrl = targetUrl.slice(0, -1);
  const healthEndpoint = (targetUrl ? targetUrl : "") + "/api/health";
  
  alertEl.style.display = "block";
  alertEl.style.background = "var(--status-warning-bg)";
  alertEl.style.color = "var(--status-warning-text)";
  alertEl.style.border = "1px solid var(--status-warning-border)";
  alertEl.textContent = "Testing connection to " + healthEndpoint + "...";
  
  try {
    const res = await fetch(healthEndpoint, { method: "GET" });
    if (res.ok) {
      const data = await res.json();
      alertEl.style.background = "var(--status-success-bg)";
      alertEl.style.color = "var(--status-success-text)";
      alertEl.style.border = "1px solid var(--status-success-border)";
      alertEl.textContent = `Connected! ${data.service || 'ShoeMatch AI'} (${data.total_vectors || 0} catalog vectors ready).`;
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    alertEl.style.background = "var(--status-danger-bg)";
    alertEl.style.color = "var(--status-danger-text)";
    alertEl.style.border = "1px solid var(--status-danger-border)";
    alertEl.textContent = "Connection failed (" + err.message + "). Please verify server IP and ensure run_server.py is running on port 8000.";
  }
};

window.saveServerUrl = function() {
  const input = document.getElementById("input-server-url");
  if (!input) return;
  let targetUrl = input.value.trim();
  if (targetUrl.endsWith("/")) targetUrl = targetUrl.slice(0, -1);
  
  try {
    if (targetUrl && targetUrl !== window.location.origin) {
      localStorage.setItem("shoematch_api_base_url", targetUrl);
    } else {
      localStorage.removeItem("shoematch_api_base_url");
    }
  } catch (e) {}
  
  window.closeServerSettingsModal();
  if (window.showToast) window.showToast("Server base URL updated to " + (targetUrl || "same-origin"), "success");
  setTimeout(() => window.location.reload(), 400);
};

window.resetServerUrl = function() {
  try {
    localStorage.removeItem("shoematch_api_base_url");
  } catch (e) {}
  const input = document.getElementById("input-server-url");
  if (input) input.value = window.location.origin;
  window.closeServerSettingsModal();
  if (window.showToast) window.showToast("Server URL reset to same-origin", "success");
  setTimeout(() => window.location.reload(), 400);
};

// Theme Toggle Functions
window.toggleTheme = function() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme") === "dark" ? "dark" : "light";
  const target = current === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", target);
  try {
    localStorage.setItem("shoematch_theme", target);
  } catch(e) {}
  window.updateThemeToggleUI(target);
};

window.updateThemeToggleUI = function(theme) {
  const btns = document.querySelectorAll(".btn-theme-toggle");
  const isDark = theme === "dark";
  btns.forEach(btn => {
    btn.setAttribute("aria-pressed", isDark ? "true" : "false");
    btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    btn.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");
    const moon = btn.querySelector(".icon-moon");
    const sun = btn.querySelector(".icon-sun");
    if (moon) moon.style.display = isDark ? "none" : "block";
    if (sun) sun.style.display = isDark ? "block" : "none";
  });
};

document.addEventListener("DOMContentLoaded", () => {
  const getApiUrl = window.getApiUrl;
  const getImageUrl = window.getImageUrl;

  // Sync Theme Toggle UI
  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
  window.updateThemeToggleUI(currentTheme);
  // Application State
  const state = {
    currentTab: "match-tab",
    selectedQueryFile: null,
    catalog: [],
    logs: [],
    benchmarkData: null,
    modalFiles: [],
    cameraStream: null,
    cameraFacingMode: "environment"
  };

  // DOM Elements
  const elements = {
    // Sidebar & Navigation
    sidebar: document.getElementById("sidebar"),
    btnToggleSidebar: document.getElementById("btn-toggle-sidebar"),
    btnTopbarToggle: document.getElementById("btn-topbar-toggle"),
    navButtons: document.querySelectorAll(".nav-item"),
    tabPanes: document.querySelectorAll(".tab-pane"),
    pageTitle: document.getElementById("page-title"),
    pageDescription: document.getElementById("page-description"),
    navCatalogCount: document.getElementById("nav-catalog-count"),
    btnOpenAddModal: document.getElementById("btn-open-add-modal"),

    // Visual Match Studio
    queryDropzone: document.getElementById("query-dropzone"),
    queryFileInput: document.getElementById("query-file-input"),
    cameraNativeInput: document.getElementById("camera-native-input"),
    dropPrompt: document.getElementById("drop-prompt"),
    queryPreviewContainer: document.getElementById("query-preview-container"),
    queryPreviewImg: document.getElementById("query-preview-img"),
    btnBrowseFile: document.getElementById("btn-browse-file"),
    btnChangeImage: document.getElementById("btn-change-image"),
    btnOpenCamera: document.getElementById("btn-open-camera"),
    btnRecaptureCamera: document.getElementById("btn-recapture-camera"),
    btnClearQuery: document.getElementById("btn-clear-query"),
    btnRunMatch: document.getElementById("btn-run-match"),
    resultsEmpty: document.getElementById("results-empty"),
    resultsLoading: document.getElementById("results-loading"),
    matchesList: document.getElementById("matches-list"),
    resultsMetaText: document.getElementById("results-meta-text"),
    latencyBadge: document.getElementById("latency-badge"),
    latencyText: document.getElementById("latency-text"),
    detectedCategoryBadge: document.getElementById("detected-category-badge"),
    detectedCatIcon: document.getElementById("detected-cat-icon"),
    detectedCatText: document.getElementById("detected-cat-text"),

    // Camera Modal
    cameraModal: document.getElementById("camera-modal"),
    cameraFeedContainer: document.getElementById("camera-feed-container"),
    cameraErrorContainer: document.getElementById("camera-error-container"),
    cameraErrorMessage: document.getElementById("camera-error-message"),
    btnCameraErrorFallback: document.getElementById("btn-camera-error-fallback"),
    btnCloseCamera: document.getElementById("btn-close-camera"),
    btnSnapPhoto: document.getElementById("btn-snap-photo"),
    btnSwitchCamera: document.getElementById("btn-switch-camera"),
    cameraVideo: document.getElementById("camera-video"),
    cameraCanvas: document.getElementById("camera-canvas"),
    cameraLoadingNotice: document.getElementById("camera-loading-notice"),

    // Catalog
    catalogSearchInput: document.getElementById("catalog-search-input"),
    catalogCategoryFilter: document.getElementById("catalog-category-filter"),
    btnRefreshCatalog: document.getElementById("btn-refresh-catalog"),
    catalogGrid: document.getElementById("catalog-grid"),

    // Logs
    logsTbody: document.getElementById("logs-tbody"),
    btnRefreshLogs: document.getElementById("btn-refresh-logs"),

    // Modals
    addModal: document.getElementById("add-modal"),
    btnCloseAddModal: document.getElementById("btn-close-add-modal"),
    btnCancelAdd: document.getElementById("btn-cancel-add"),
    addDesignForm: document.getElementById("add-design-form"),
    modalDropzone: document.getElementById("modal-dropzone"),
    modalFilesInput: document.getElementById("modal-files-input"),
    modalPreviews: document.getElementById("modal-previews"),

    detailModal: document.getElementById("detail-modal"),
    btnCloseDetailModal: document.getElementById("btn-close-detail-modal"),
    detailTitle: document.getElementById("detail-title"),
    detailModalBody: document.getElementById("detail-modal-body"),

    toastContainer: document.getElementById("toast-container")
  };

  // Tab Configurations
  const tabTitles = {
    "match-tab": {
      title: "Visual Match Studio",
      desc: "Upload a shoe photo to query the factory reference catalog and inspect Top-3 ranked matches."
    },
    "catalog-tab": {
      title: "Design Catalog Explorer",
      desc: "Browse manufactured shoe models, multi-angle reference photos, and specifications."
    },
    "logs-tab": {
      title: "Audit & Query History Logs",
      desc: "Review previous shoe recognition queries, confidence scores, and latency metrics."
    },
    "locations-tab": {
      title: "Location Hierarchy & Warehouse Management",
      desc: "Manage physical warehouse structure (Shoe Match Zone → Shelf → Drawer → Slot) and assign catalog designs."
    },
    "admin-tab": {
      title: "Admin Operations & User Management",
      desc: "Manage system access, user roles, security policies, and catalog database statistics."
    }
  };

  // ==========================================
  // Initialization & Stats
  // ==========================================
  async function init() {
    restoreSidebarState();
    setupEventListeners();
    await window.checkAuthSession();

    // Check for native app first-run server IP prompt
    const savedServerUrl = window.getApiBaseUrl();
    const isNativeContext = Boolean(
      (window.Capacitor && window.Capacitor.isNativePlatform()) ||
      window.location.protocol === "file:" ||
      window.location.protocol === "capacitor:" ||
      window.location.protocol === "tauri:"
    );

    if (isNativeContext && !savedServerUrl) {
      setTimeout(() => {
        window.openServerSettingsModal();
        if (window.showToast) {
          window.showToast("Welcome to ShoeMatch AI Native! Please enter your warehouse server IP address.", "warning");
        }
      }, 500);
    }

    await fetchStats();
    await fetchCatalog();
    await fetchLogs();
  }

  function toggleSidebar() {
    if (!elements.sidebar) return;
    const isCollapsed = elements.sidebar.classList.toggle("collapsed");
    localStorage.setItem("sidebar_collapsed", isCollapsed ? "true" : "false");
  }

  function restoreSidebarState() {
    if (localStorage.getItem("sidebar_collapsed") === "true" && elements.sidebar) {
      elements.sidebar.classList.add("collapsed");
    }
  }

  async function fetchStats() {
    try {
      const res = await fetch(getApiUrl("/api/stats"));
      if (res.ok) {
        const stats = await res.json();
        if (elements.navCatalogCount) elements.navCatalogCount.textContent = stats.total_designs || 0;
        if (elements.sidebarVectors) elements.sidebarVectors.textContent = `${stats.total_reference_images} photos`;
        if (elements.sidebarLatency && stats.average_latency_ms) {
          elements.sidebarLatency.textContent = `${stats.average_latency_ms} ms`;
        }
      }
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  }

  // ==========================================
  // Navigation & Tab Switching
  // ==========================================
  function switchTab(tabId) {
    state.currentTab = tabId;

    document.querySelectorAll(".nav-item[data-tab]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });

    document.querySelectorAll(".tab-pane").forEach(pane => {
      pane.classList.toggle("active", pane.id === tabId);
    });

    // Update Topbar
    const config = tabTitles[tabId] || tabTitles["match-tab"];
    elements.pageTitle.textContent = config.title;
    elements.pageDescription.textContent = config.desc;

    // Refresh Tab-specific data
    if (tabId === "catalog-tab") fetchCatalog();
    if (tabId === "logs-tab") fetchLogs();
    if (tabId === "locations-tab") fetchLocationHierarchy();
    if (tabId === "admin-tab") fetchAdminUsers();
  }
  window.switchTab = switchTab;

  // ==========================================
  // Event Listeners Setup
  // ==========================================
  function setupEventListeners() {
    // Navigation
    document.querySelectorAll(".nav-item[data-tab]").forEach(btn => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    // Dropzone Click (Browse when clicking inside empty box)
    if (elements.queryDropzone) {
      elements.queryDropzone.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("label") || e.target.closest(".preview-overlay") || e.target.closest(".query-source-toolbar")) {
          return;
        }
        if (!state.selectedQueryFile) {
          elements.queryFileInput.click();
        }
      });
    }
    if (elements.queryFileInput) elements.queryFileInput.addEventListener("change", handleQueryFileSelect);

    // Native Camera Input Change Listener (Triggers instant matching)
    if (elements.cameraNativeInput) {
      elements.cameraNativeInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
          setQueryFile(e.target.files[0], true);
          showToast("Photo captured from device camera!", "success");
        }
      });
    }

    // Dropzone Drag Events
    if (elements.queryDropzone) {
      elements.queryDropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        elements.queryDropzone.classList.add("drag-over");
      });
      elements.queryDropzone.addEventListener("dragleave", () => {
        elements.queryDropzone.classList.remove("drag-over");
      });
      elements.queryDropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        elements.queryDropzone.classList.remove("drag-over");
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          setQueryFile(e.dataTransfer.files[0]);
        }
      });
    }

    // Clipboard Paste Support (Ctrl+V)
    window.addEventListener("paste", (e) => {
      if (e.clipboardData && e.clipboardData.files.length > 0) {
        const file = e.clipboardData.files[0];
        if (file.type.startsWith("image/")) {
          setQueryFile(file);
          showToast("Image pasted from clipboard!", "success");
        }
      }
    });

    // Sidebar Toggle (Full View Slider Mode)
    if (elements.btnToggleSidebar) elements.btnToggleSidebar.addEventListener("click", toggleSidebar);
    if (elements.btnTopbarToggle) elements.btnTopbarToggle.addEventListener("click", toggleSidebar);

    // Clear and Match Buttons
    if (elements.btnClearQuery) elements.btnClearQuery.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      resetQueryStudio();
    });
    if (elements.btnRunMatch) elements.btnRunMatch.addEventListener("click", executeVisualMatch);

    // Catalog & Design Library Controls
    let searchDebounceTimer = null;
    if (elements.catalogSearchInput) {
      elements.catalogSearchInput.addEventListener("input", (e) => {
        state.catalogSearchQuery = e.target.value.trim();
        state.catalogCurrentPage = 1;
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          fetchCatalog();
        }, 300);
      });
    }

    if (elements.catalogCategoryFilter) {
      elements.catalogCategoryFilter.addEventListener("change", (e) => {
        state.catalogCategoryFilter = e.target.value;
        state.catalogCurrentPage = 1;
        fetchCatalog();
      });
    }

    const statusFilter = document.getElementById("catalog-status-filter");
    if (statusFilter) {
      statusFilter.addEventListener("change", (e) => {
        state.catalogStatusFilter = e.target.value;
        state.catalogCurrentPage = 1;
        fetchCatalog();
      });
    }

    const sortSelect = document.getElementById("catalog-sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", (e) => {
        state.catalogSortOrder = e.target.value;
        state.catalogCurrentPage = 1;
        fetchCatalog();
      });
    }

    // Location Management Controls
    const locSearch = document.getElementById("loc-search-input");
    let locSearchTimer = null;
    if (locSearch) {
      locSearch.addEventListener("input", (e) => {
        state.locationsSearchQuery = e.target.value.trim();
        clearTimeout(locSearchTimer);
        locSearchTimer = setTimeout(() => {
          if (state.locationsViewMode === "table") fetchSlotsTable();
          else renderLocationHierarchy();
        }, 300);
      });
    }

    const locZoneFilter = document.getElementById("loc-zone-filter");
    if (locZoneFilter) {
      locZoneFilter.addEventListener("change", (e) => {
        state.locationsZoneFilter = e.target.value;
        if (state.locationsViewMode === "table") fetchSlotsTable();
        else renderLocationHierarchy();
      });
    }

    const locOccFilter = document.getElementById("loc-occupancy-filter");
    if (locOccFilter) {
      locOccFilter.addEventListener("change", (e) => {
        state.locationsOccupancyFilter = e.target.value;
        if (state.locationsViewMode === "table") fetchSlotsTable();
        else renderLocationHierarchy();
      });
    }

    if (elements.btnRefreshCatalog) elements.btnRefreshCatalog.addEventListener("click", fetchCatalog);
    if (elements.btnRefreshLogs) elements.btnRefreshLogs.addEventListener("click", fetchLogs);

    // Modal Events & Backdrop Dismissal
    if (elements.btnOpenAddModal) elements.btnOpenAddModal.addEventListener("click", openAddModal);
    if (elements.btnCloseAddModal) elements.btnCloseAddModal.addEventListener("click", closeAddModal);
    if (elements.btnCancelAdd) elements.btnCancelAdd.addEventListener("click", closeAddModal);
    if (elements.btnCloseDetailModal) elements.btnCloseDetailModal.addEventListener("click", () => elements.detailModal.style.display = "none");

    // Close Modals on Backdrop Click (Clicking outside modal dialog)
    if (elements.detailModal) {
      elements.detailModal.addEventListener("click", (e) => {
        if (e.target === elements.detailModal) elements.detailModal.style.display = "none";
      });
    }
    if (elements.addModal) {
      elements.addModal.addEventListener("click", (e) => {
        if (e.target === elements.addModal) closeAddModal();
      });
    }
    if (elements.cameraModal) {
      elements.cameraModal.addEventListener("click", (e) => {
        if (e.target === elements.cameraModal) closeCameraModal();
      });
    }

    // Global Escape Key Listener for Modals
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" || e.key === "Esc") {
        if (elements.detailModal && elements.detailModal.style.display !== "none") {
          elements.detailModal.style.display = "none";
        }
        if (elements.addModal && elements.addModal.style.display !== "none") {
          closeAddModal();
        }
        if (elements.cameraModal && elements.cameraModal.style.display !== "none") {
          closeCameraModal();
        }
      }
    });

    // Camera Capture Modal Controls
    if (elements.btnCameraErrorFallback) {
      elements.btnCameraErrorFallback.addEventListener("click", () => {
        closeCameraModal();
        if (elements.cameraNativeInput) elements.cameraNativeInput.click();
      });
    }
    if (elements.btnCloseCamera) elements.btnCloseCamera.addEventListener("click", closeCameraModal);
    if (elements.btnSnapPhoto) elements.btnSnapPhoto.addEventListener("click", snapPhotoFromCamera);
    if (elements.btnSwitchCamera) elements.btnSwitchCamera.addEventListener("click", switchCamera);

    // Modal Drag and Drop
    if (elements.modalDropzone) {
      elements.modalDropzone.addEventListener("click", () => elements.modalFilesInput.click());
      elements.modalDropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        elements.modalDropzone.style.borderColor = "var(--brand-primary)";
      });
      elements.modalDropzone.addEventListener("dragleave", () => {
        elements.modalDropzone.style.borderColor = "";
      });
      elements.modalDropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        elements.modalDropzone.style.borderColor = "";
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          Array.from(e.dataTransfer.files).forEach(f => {
            if (f.type.startsWith("image/")) state.modalFiles.push(f);
          });
          renderModalPreviews();
        }
      });
    }
    if (elements.modalFilesInput) elements.modalFilesInput.addEventListener("change", handleModalFilesSelect);
    if (elements.addDesignForm) elements.addDesignForm.addEventListener("submit", submitNewDesign);
  }

  // ==========================================
  // Visual Matching Logic
  // ==========================================
  function handleQueryFileSelect(e) {
    if (e.target.files && e.target.files.length > 0) {
      setQueryFile(e.target.files[0]);
    }
  }

  function setQueryFile(file, autoMatch = true) {
    if (!file) return;

    state.selectedQueryFile = file;

    // Show Image Preview
    try {
      const objectUrl = URL.createObjectURL(file);
      elements.queryPreviewImg.src = objectUrl;
    } catch (e) {
      console.warn("Preview createObjectURL notice:", e);
    }

    elements.dropPrompt.style.display = "none";
    elements.queryPreviewContainer.style.display = "block";
    elements.btnClearQuery.style.display = "inline-block";
    elements.btnRunMatch.disabled = false;

    // Prepare visual results area
    elements.resultsEmpty.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsLoading.style.display = "block";
    elements.resultsMetaText.textContent = "Searching footwear catalog...";
    elements.latencyBadge.style.display = "none";
    if (elements.detectedCategoryBadge) elements.detectedCategoryBadge.style.display = "none";

    // Smoothly scroll to results on mobile devices
    const resultsCard = document.querySelector(".results-card");
    if (resultsCard && window.innerWidth < 900) {
      setTimeout(() => {
        resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    }

    // Auto-execute visual match immediately
    if (autoMatch) {
      setTimeout(() => executeVisualMatch(), 30);
    }
  }

  function resetQueryStudio() {
    state.selectedQueryFile = null;
    elements.queryFileInput.value = "";
    if (elements.cameraNativeInput) elements.cameraNativeInput.value = "";
    elements.dropPrompt.style.display = "block";
    elements.queryPreviewContainer.style.display = "none";
    elements.queryPreviewImg.src = "";
    elements.btnClearQuery.style.display = "none";
    elements.btnRunMatch.disabled = true;

    elements.resultsEmpty.innerHTML = `
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          <path d="M11 8v6M8 11h6"/>
        </svg>
      </div>
      <h4>No Query Executed Yet</h4>
      <p>Upload a shoe or slipper image on the left and click "Find Matches in Catalog" to view side-by-side rankings.</p>
    `;
    elements.resultsEmpty.style.display = "block";
    elements.resultsLoading.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsMetaText.textContent = "Awaiting query image";
    elements.latencyBadge.style.display = "none";
    if (elements.detectedCategoryBadge) elements.detectedCategoryBadge.style.display = "none";
  }

  async function executeVisualMatch() {
    if (!state.selectedQueryFile) return;

    // UI Loading State & Pipeline Progress Widget
    elements.resultsEmpty.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsLoading.style.display = "block";
    elements.btnRunMatch.disabled = true;
    elements.resultsMetaText.textContent = "Executing search pipeline...";
    if (elements.detectedCategoryBadge) elements.detectedCategoryBadge.style.display = "none";

    // Reset pipeline stage items
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById(`stage-${i}`);
      if (el) el.className = "pipeline-stage-item";
    }

    const s1 = document.getElementById("stage-1");
    if (s1) s1.className = "pipeline-stage-item active";

    const stageTimer1 = setTimeout(() => {
      if (s1) s1.className = "pipeline-stage-item completed";
      const s2 = document.getElementById("stage-2");
      if (s2) s2.className = "pipeline-stage-item active";
    }, 180);

    const stageTimer2 = setTimeout(() => {
      const s2 = document.getElementById("stage-2");
      if (s2) s2.className = "pipeline-stage-item completed";
      const s3 = document.getElementById("stage-3");
      if (s3) s3.className = "pipeline-stage-item active";
    }, 420);

    const stageTimer3 = setTimeout(() => {
      const s3 = document.getElementById("stage-3");
      if (s3) s3.className = "pipeline-stage-item completed";
      const s4 = document.getElementById("stage-4");
      if (s4) s4.className = "pipeline-stage-item active";
    }, 650);

    const fileToUpload = state.selectedQueryFile;
    const filename = fileToUpload.name || `mobile_photo_${Date.now()}.jpg`;

    const formData = new FormData();
    formData.append("file", fileToUpload, filename);
    formData.append("top_k", "3");

    try {
      const response = await fetch(getApiUrl("/api/match"), {
        method: "POST",
        body: formData
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);

      for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`stage-${i}`);
        if (el) el.className = "pipeline-stage-item completed";
      }

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Matching failed");
      }

      const data = await response.json();
      renderMatchResults(data);
      fetchStats();
    } catch (err) {
      console.error("Match error:", err);
      showToast(err.message, "error");
      elements.resultsEmpty.style.display = "block";
    } finally {
      elements.resultsLoading.style.display = "none";
      elements.btnRunMatch.disabled = false;
    }
  }

  function renderMatchResults(data) {
    elements.matchesList.innerHTML = "";
    elements.resultsLoading.style.display = "none";

    // Non-footwear guard: No shoe or slipper found
    if (data.is_footwear_detected === false || data.detected_category === "none") {
      if (elements.detectedCategoryBadge) {
        elements.detectedCategoryBadge.style.display = "inline-flex";
        if (elements.detectedCatIcon) elements.detectedCatIcon.textContent = "🚫";
        if (elements.detectedCatText) elements.detectedCatText.textContent = "No Shoe / Slipper Detected";
      }
      elements.resultsEmpty.style.display = "block";
      elements.resultsEmpty.querySelector("h4").textContent = "🚫 No Shoe Detected";
      elements.resultsEmpty.querySelector("p").textContent = data.message || "The uploaded image does not appear to contain a shoe or slipper. Please upload a clear photo of footwear.";
      elements.matchesList.style.display = "none";
      elements.resultsMetaText.textContent = "Non-footwear image uploaded";
      showToast("No shoe or slipper detected in image", "warning");
      return;
    }

    // Render detected category badge
    if (data.detected_category && elements.detectedCategoryBadge) {
      elements.detectedCategoryBadge.style.display = "inline-flex";
      const isSlipper = data.detected_category.toLowerCase() === "slipper";
      if (elements.detectedCatIcon) elements.detectedCatIcon.textContent = isSlipper ? "🩴" : "👟";
      if (elements.detectedCatText) elements.detectedCatText.textContent = `Detected: ${isSlipper ? 'Slipper' : 'Shoe'} (${data.category_confidence_pct || 95}%)`;
    }

    if (!data.matches || data.matches.length === 0) {
      elements.resultsEmpty.style.display = "block";
      const catName = data.detected_category ? data.detected_category.toUpperCase() : "Category";
      elements.resultsEmpty.querySelector("h4").textContent = `No ${catName} Matches in Catalog`;
      elements.resultsEmpty.querySelector("p").textContent = data.message || "No reference designs exist for this category in the catalog.";
      return;
    }

    elements.resultsEmpty.style.display = "none";
    elements.matchesList.style.display = "flex";
    const catLabel = data.detected_category ? `${data.detected_category.toUpperCase()} Matches` : "Matches";
    elements.resultsMetaText.textContent = `Found Top 3 ${catLabel} (${data.total_catalog_designs} catalog designs)`;

    // Latency badge
    elements.latencyBadge.style.display = "inline-flex";
    elements.latencyText.textContent = `${data.latency_ms} ms`;

    // Render each of Top 3 matches
    data.matches.forEach((m) => {
      const card = document.createElement("div");
      card.className = `match-item-card ${m.match_color}`;
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("title", `Click to preview full specs and shelf coordinates for ${m.design_name} (${m.design_id})`);

      const rankLabels = ["#1 Best Match", "#2 Second Best", "#3 Third Best"];
      const rankLabel = rankLabels[m.rank - 1] || `#${m.rank} Match`;

      // Build angle thumbnails
      let angleThumbsHtml = "";
      if (m.all_angles && m.all_angles.length > 0) {
        angleThumbsHtml = `
          <div class="angles-strip">
            <span style="font-size: 0.7rem; color: var(--text-muted);">Angles:</span>
            ${m.all_angles.map(a => `
              <img src="${getImageUrl(a.image_path)}" 
                   class="angle-thumb ${a.image_path === m.best_matching_image_url ? 'active' : ''}" 
                   title="Angle: ${a.angle}" 
                   onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';"
                   onclick="event.stopPropagation(); swapMatchImage(this, '${m.design_id}')">
            `).join("")}
          </div>
        `;
      }

      const shelfLocation = m.shelf_location || "Warehouse A - Rack 03 - Shelf B-02";

      const confLevel = m.confidence_pct >= 85 ? "high" : (m.confidence_pct >= 70 ? "medium" : "low");
      const levelLabel = m.confidence_pct >= 85 ? "Strong Match" : (m.confidence_pct >= 70 ? "Variant" : "Low Certitude");

      card.innerHTML = `
        <div class="match-img-box" id="img-box-${m.design_id}">
          <img src="${getImageUrl(m.best_matching_image_url)}" alt="${m.design_name}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
          <span class="match-angle-tag">${m.best_matching_angle}</span>
        </div>

        <div class="match-details">
          <div class="match-card-header">
            <span class="match-rank-tag">${rankLabel}</span>
            <span class="precision-confidence-badge ${confLevel}">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <span>${m.confidence_pct}% ${levelLabel}</span>
            </span>
          </div>

          <h4 class="match-title">${m.design_name}</h4>
          <span class="match-sku">SKU: ${m.design_id} &bull; ${m.category}</span>
          
          <div class="match-card-shelf-badge" title="Warehouse Location Coordinate">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <span>${shelfLocation}</span>
          </div>

          <p class="match-desc" style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 6px;">${m.description || "Factory specification model."}</p>
          ${angleThumbsHtml}
          ${m.dominant_colors && m.dominant_colors.length > 0 ? `
            <div class="color-palette-strip" style="display: flex; gap: 6px; align-items: center; margin: 6px 0;">
              <span style="font-size: 0.72rem; color: var(--text-muted); font-weight: 500;">Colors:</span>
              ${m.dominant_colors.map(c => `
                <span style="width: 14px; height: 14px; border-radius: 50%; background: ${c.hex}; border: 1px solid rgba(0,0,0,0.15); display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.1);" title="${c.hex} (${c.percentage}%)"></span>
              `).join("")}
            </div>
          ` : ''}
          
          <div class="match-action-hint" style="margin-top: 6px;">
            <button type="button" class="btn-inspect-quick-action" style="background: none; border: none; color: var(--brand-primary); font-size: 0.78rem; font-weight: 700; cursor: pointer; padding: 0; display: inline-flex; align-items: center; gap: 4px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
              <span>Inspect Full Specs & Warehouse Shelf &rarr;</span>
            </button>
          </div>

          <div class="match-feedback-row" onclick="event.stopPropagation();">
            <span class="feedback-label" style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">Feedback:</span>
            <button type="button" class="btn-feedback correct" title="Confirm correct match" onclick="event.stopPropagation(); submitFeedback(${data.query_id || 'null'}, 'correct', '${m.design_id}', this)">👍 Correct</button>
            <button type="button" class="btn-feedback wrong" title="Report wrong design match" onclick="event.stopPropagation(); submitFeedback(${data.query_id || 'null'}, 'wrong_match', '${m.design_id}', this)">👎 Wrong</button>
            <button type="button" class="btn-feedback not-in-catalog" title="Footwear is not in catalog" onclick="event.stopPropagation(); submitFeedback(${data.query_id || 'null'}, 'not_in_catalog', null, this)">❓ Not in Catalog</button>
          </div>
        </div>
      `;

      card.onclick = (e) => {
        if (e.target && e.target.closest(".match-feedback-row")) {
          return;
        }
        openShoeInspectionModal(m.design_id, m);
      };
      card.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openShoeInspectionModal(m.design_id, m);
        }
      };

      elements.matchesList.appendChild(card);
    });
  }

  // Submit User Feedback on Search Result
  window.submitFeedback = async function(queryId, verdict, designId, btnElem) {
    try {
      const res = await fetch(window.getApiUrl("/api/feedback"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query_id: queryId,
          user_verdict: verdict,
          correct_design_id: designId,
          notes: ""
        })
      });
      if (res.ok) {
        const row = btnElem.closest(".match-feedback-row");
        if (row) {
          row.innerHTML = `<span style="color: var(--color-green); font-weight: 600; font-size: 0.76rem;">✓ Feedback recorded (${verdict.replace('_', ' ')})</span>`;
        }
        showToast("Feedback recorded. Thank you!", "success");
      }
    } catch (err) {
      console.error("Failed to submit feedback:", err);
      showToast("Failed to submit feedback", "error");
    }
  };

  // Swap preview angle photo when user clicks an angle thumbnail
  window.swapMatchImage = function(thumbEl, designId) {
    const box = document.getElementById(`img-box-${designId}`);
    if (box) {
      const mainImg = box.querySelector("img");
      const angleTag = box.querySelector(".match-angle-tag");
      if (mainImg) mainImg.src = thumbEl.src;
      if (angleTag) angleTag.textContent = thumbEl.title.replace("Angle: ", "");
        const parent = thumbEl.parentElement;
        if (parent) {
          parent.querySelectorAll(".angle-thumb").forEach(t => t.classList.remove("active"));
          thumbEl.classList.add("active");
        }
      }
    };

    // ==========================================
    // Catalog & Design Library Explorer
    // ==========================================
    state.catalogViewMode = localStorage.getItem("shoematch_catalog_view") || "grid";
    state.catalogCurrentPage = 1;
    state.catalogPerPage = 10;
    state.catalogSearchQuery = "";
    state.catalogCategoryFilter = "";
    state.catalogStatusFilter = "";
    state.catalogSortOrder = "newest";

    window.setCatalogViewMode = function(mode) {
      state.catalogViewMode = mode;
      try { localStorage.setItem("shoematch_catalog_view", mode); } catch (e) {}
      
      const gridBtn = document.getElementById("btn-view-grid");
      const listBtn = document.getElementById("btn-view-list");
      const gridWrap = document.getElementById("catalog-grid");
      const listWrap = document.getElementById("catalog-list-wrap");

      if (mode === "list") {
        if (gridBtn) gridBtn.classList.remove("active");
        if (listBtn) listBtn.classList.add("active");
        if (gridWrap) gridWrap.style.display = "none";
        if (listWrap) listWrap.style.display = "block";
      } else {
        if (gridBtn) gridBtn.classList.add("active");
        if (listBtn) listBtn.classList.remove("active");
        if (gridWrap) gridWrap.style.display = "grid";
        if (listWrap) listWrap.style.display = "none";
      }

      renderCatalog();
    };

    window.handleCatalogPerPageChange = function(val) {
      state.catalogPerPage = parseInt(val, 10) || 10;
      state.catalogCurrentPage = 1;
      fetchCatalog();
    };

    window.changeCatalogPage = function(delta) {
      const totalPages = Math.ceil((state.catalogTotal || 0) / state.catalogPerPage) || 1;
      const target = state.catalogCurrentPage + delta;
      if (target >= 1 && target <= totalPages) {
        state.catalogCurrentPage = target;
        fetchCatalog();
      }
    };

    function formatLocationDetails(d) {
      const parts = [];
      if (d.shelf_location) parts.push(`Shelf: ${d.shelf_location}`);
      if (d.drawer) parts.push(`Drawer: ${d.drawer}`);
      if (d.slot) parts.push(`Slot: ${d.slot}`);
      if (d.shoe_match_tag) parts.push(`Tag: ${d.shoe_match_tag}`);
      return parts.length > 0 ? parts.join(" • ") : "Warehouse Main Reserve";
    }

    async function fetchCatalog() {
      try {
        const qParams = new URLSearchParams();
        if (state.catalogSearchQuery) qParams.set("search", state.catalogSearchQuery);
        if (state.catalogCategoryFilter) qParams.set("category", state.catalogCategoryFilter);
        if (state.catalogStatusFilter) qParams.set("status", state.catalogStatusFilter);
        if (state.catalogSortOrder) qParams.set("sort", state.catalogSortOrder);
        qParams.set("page", state.catalogCurrentPage);
        qParams.set("limit", state.catalogPerPage);

        const res = await window.authenticatedFetch(getApiUrl(`/api/designs?${qParams.toString()}`));
        if (res.ok) {
          const data = await res.json();
          state.catalog = data.designs || [];
          state.catalogTotal = data.total || 0;
          
          if (elements.navCatalogCount) elements.navCatalogCount.textContent = state.catalogTotal;
          renderCatalog();
        }
      } catch (err) {
        console.error("Failed to fetch catalog:", err);
      }
    }

    function renderCatalog() {
      const mode = state.catalogViewMode || "grid";
      const gridBtn = document.getElementById("btn-view-grid");
      const listBtn = document.getElementById("btn-view-list");
      const gridWrap = document.getElementById("catalog-grid");
      const listWrap = document.getElementById("catalog-list-wrap");

      if (mode === "list") {
        if (gridBtn) gridBtn.classList.remove("active");
        if (listBtn) listBtn.classList.add("active");
        if (gridWrap) gridWrap.style.display = "none";
        if (listWrap) listWrap.style.display = "block";
      } else {
        if (gridBtn) gridBtn.classList.add("active");
        if (listBtn) listBtn.classList.remove("active");
        if (gridWrap) gridWrap.style.display = "grid";
        if (listWrap) listWrap.style.display = "none";
      }

      const total = state.catalogTotal || 0;
      const totalPages = Math.ceil(total / state.catalogPerPage) || 1;
      state.catalogCurrentPage = Math.min(state.catalogCurrentPage, totalPages);

      const infoEl = document.getElementById("catalog-pagination-info");
      if (infoEl) {
        const startIdx = total === 0 ? 0 : (state.catalogCurrentPage - 1) * state.catalogPerPage + 1;
        const endIdx = Math.min(state.catalogCurrentPage * state.catalogPerPage, total);
        infoEl.textContent = `Showing ${startIdx}-${endIdx} of ${total} entries (Page ${state.catalogCurrentPage} of ${totalPages})`;
      }
      const prevBtn = document.getElementById("btn-catalog-prev");
      const nextBtn = document.getElementById("btn-catalog-next");
      if (prevBtn) prevBtn.disabled = (state.catalogCurrentPage <= 1);
      if (nextBtn) nextBtn.disabled = (state.catalogCurrentPage >= totalPages);

      if (state.catalogViewMode === "list") {
        renderCatalogList(state.catalog);
      } else {
        renderCatalogGrid(state.catalog);
      }
    }

    function renderCatalogGrid(designs) {
      if (!elements.catalogGrid) return;
      elements.catalogGrid.innerHTML = "";

      if (!designs || designs.length === 0) {
        elements.catalogGrid.innerHTML = `
          <div class="results-empty" style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
            <h4>No Designs Found</h4>
            <p>No catalog items match your search, category, or status filter.</p>
          </div>
        `;
        return;
      }

      designs.forEach(d => {
        const card = document.createElement("div");
        card.className = "catalog-card";
        card.onclick = () => openShoeInspectionModal(d.design_id, null);

        const isArchived = d.is_archived === 1;
        const isActive = d.is_active !== 0;
        let statusBadgeHtml = '<span class="catalog-status-badge active">Active</span>';
        if (isArchived) {
          statusBadgeHtml = '<span class="catalog-status-badge archived">Archived</span>';
        } else if (!isActive) {
          statusBadgeHtml = '<span class="catalog-status-badge deactivated">Inactive</span>';
        }

        const locationStr = formatLocationDetails(d);
        const thumb = window.getLogThumbnailUrl(d.thumbnail_path);

        card.innerHTML = `
          <div class="catalog-card-img">
            <img src="${thumb}" alt="${d.name}" loading="lazy" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><rect x=\'3\' y=\'3\' width=\'18\' height=\'18\' rx=\'2\'/><path d=\'M8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z\'/><path d=\'M21 15l-5-5L5 21\'/></svg>';">
            <span class="catalog-card-pill">${d.design_id}</span>
            ${statusBadgeHtml}
            <span class="catalog-card-count">${d.image_count || 1} angles</span>
          </div>
          <div class="catalog-card-body">
            <h4 class="catalog-card-title">${d.name}</h4>
            <span class="catalog-card-cat">${d.category} &bull; ${d.created_by || 'Design Team'}</span>
            
            <div class="catalog-location-pill" style="margin: 8px 0;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <span>${locationStr}</span>
            </div>

            <p class="catalog-card-desc">${d.description || "Manufactured catalog specification."}</p>
          </div>
        `;

        elements.catalogGrid.appendChild(card);
      });
    }

    function renderCatalogList(designs) {
      const tbody = document.getElementById("catalog-list-tbody");
      if (!tbody) return;
      tbody.innerHTML = "";

      if (!designs || designs.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">
              No catalog items match your criteria.
            </td>
          </tr>
        `;
        return;
      }

      designs.forEach(d => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.onclick = () => openShoeInspectionModal(d.design_id, null);

        const isArchived = d.is_archived === 1;
        const isActive = d.is_active !== 0;
        let statusBadgeHtml = '<span class="log-status-badge success">Active</span>';
        if (isArchived) {
          statusBadgeHtml = '<span class="log-status-badge danger">Archived</span>';
        } else if (!isActive) {
          statusBadgeHtml = '<span class="log-status-badge warning">Inactive</span>';
        }

        const locationStr = formatLocationDetails(d);
        const thumb = window.getLogThumbnailUrl(d.thumbnail_path);

        tr.innerHTML = `
          <td style="text-align: center; width: 64px;">
            <div class="log-thumb-frame">
              <img src="${thumb}" class="log-thumb" alt="${d.name}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><rect x=\'3\' y=\'3\' width=\'18\' height=\'18\' rx=\'2\'/><path d=\'M8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z\'/><path d=\'M21 15l-5-5L5 21\'/></svg>';">
            </div>
          </td>
          <td>
            <div style="font-weight: 700; color: var(--text-primary); font-size: 0.88rem;">${d.name}</div>
            <div style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--text-muted);">${d.design_id}</div>
          </td>
          <td><span style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary);">${d.category}</span></td>
          <td>${statusBadgeHtml}</td>
          <td>
            <div class="catalog-location-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <span>${locationStr}</span>
            </div>
          </td>
          <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); text-align: center;">${d.image_count || 1}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); openShoeInspectionModal('${d.design_id}', null);">Inspect</button>
          </td>
        `;

        tbody.appendChild(tr);
      });
    }

  // ==========================================================================
  // Full Shoe Inspection & Warehouse Shelf Location Modal
  async function openShoeInspectionModal(designId, matchDataOrConfidence) {
    console.log("[ShoeMatch] Opening inspection modal for SKU:", designId);
    const detailModal = elements.detailModal || document.getElementById("detail-modal");
    const detailModalBody = elements.detailModalBody || document.getElementById("detail-modal-body");
    if (!detailModal || !detailModalBody) {
      console.error("[ShoeMatch] Detail modal elements not found in DOM");
      return;
    }

    // Normalize match data / confidence context
    let normalizedMatch = null;
    if (matchDataOrConfidence !== undefined && matchDataOrConfidence !== null) {
      if (typeof matchDataOrConfidence === "number" || typeof matchDataOrConfidence === "string") {
        const confNum = parseFloat(matchDataOrConfidence);
        const safeConf = !isNaN(confNum) ? Math.round(confNum * 10) / 10 : 0;
        normalizedMatch = {
          rank: 1,
          confidence_pct: safeConf,
          match_level_label: safeConf >= 85 ? "Strong Match" : (safeConf >= 70 ? "Variant" : "Unique Design"),
          match_color: safeConf >= 85 ? "green" : (safeConf >= 70 ? "yellow" : "red")
        };
      } else if (typeof matchDataOrConfidence === "object") {
        const rawConf = matchDataOrConfidence.confidence_pct ?? matchDataOrConfidence.confidence ?? matchDataOrConfidence.score;
        const confNum = rawConf !== undefined && rawConf !== null ? parseFloat(rawConf) : null;
        const safeConf = confNum !== null && !isNaN(confNum) ? Math.round(confNum * 10) / 10 : null;

        normalizedMatch = {
          rank: matchDataOrConfidence.rank || 1,
          confidence_pct: safeConf,
          match_level_label: matchDataOrConfidence.match_level_label || (safeConf !== null ? (safeConf >= 85 ? "Strong Match" : (safeConf >= 70 ? "Variant" : "Unique Design")) : "Catalog Match"),
          match_color: matchDataOrConfidence.match_color || (safeConf !== null ? (safeConf >= 85 ? "green" : (safeConf >= 70 ? "yellow" : "red")) : "green"),
          cosine_similarity: matchDataOrConfidence.cosine_similarity,
          color_similarity: matchDataOrConfidence.color_similarity
        };
      }
    }

    const skuBadge = document.getElementById("detail-sku-badge");
    const titleEl = document.getElementById("detail-title");
    if (skuBadge) skuBadge.textContent = `SKU: ${designId} • Loading specifications...`;
    if (titleEl) titleEl.textContent = `Shoe Inspection & Factory Shelf Location`;

    // Display modal preview
    detailModal.style.display = "flex";
    detailModal.style.visibility = "visible";
    detailModal.style.opacity = "1";

    detailModalBody.innerHTML = `
      <div class="modal-loading-state">
        <div class="spinner"></div>
        <h4>Loading Design Specifications & Angles...</h4>
        <p>Fetching reference details and inventory coordinates for SKU <strong>${designId}</strong></p>
      </div>
    `;

    try {
      const res = await fetch(getApiUrl(`/api/designs/${designId}`));
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}: Could not load design ${designId}`);
      }
      const design = await res.json();

      if (skuBadge) skuBadge.textContent = `SKU: ${design.design_id} • ${design.category}`;
      if (titleEl) titleEl.textContent = `${design.name}`;

      const referenceImages = design.reference_images || [];
      const rawFirstImage = referenceImages.length > 0 ? referenceImages[0].image_path : (design.thumbnail_path || '/static/placeholder.jpg');
      const firstImage = getImageUrl(rawFirstImage);
      const firstAngle = referenceImages.length > 0 ? referenceImages[0].angle : 'side';

      // Match Banner HTML (if opened from match results or confidence provided)
      let matchBannerHtml = "";
      if (normalizedMatch && normalizedMatch.confidence_pct !== null) {
        const rankLabels = ["#1 Best Match", "#2 Second Best Match", "#3 Third Best Match"];
        const rankTitle = rankLabels[normalizedMatch.rank - 1] || `#${normalizedMatch.rank} Ranked Match Result`;

        matchBannerHtml = `
          <div class="preview-match-banner ${normalizedMatch.match_color}">
            <div class="preview-match-title">
              <span>${rankTitle}</span>
              <span class="preview-match-pill ${normalizedMatch.match_color}">${normalizedMatch.confidence_pct}% (${normalizedMatch.match_level_label})</span>
            </div>
            ${normalizedMatch.cosine_similarity !== undefined ? `
              <span class="preview-cosine-tag mono">Visual Cosine: ${(normalizedMatch.cosine_similarity * 100).toFixed(1)}%</span>
            ` : ''}
          </div>
        `;
      }

      // Query photo split-screen comparison button (if query image exists)
      const queryPreviewSrc = (elements.queryPreviewImg && elements.queryPreviewImg.src && elements.queryPreviewImg.src.length > 5) ? elements.queryPreviewImg.src : null;
      const hasQueryPhoto = Boolean(state.selectedQueryFile && queryPreviewSrc);

      detailModalBody.innerHTML = `
        <div class="preview-layout">
          <!-- Left Column: Gallery & High-Res Viewer -->
          <div class="preview-gallery-col">
            <div class="preview-main-viewer" id="preview-stage-box">
              <img id="preview-active-image" src="${firstImage}" alt="${design.name}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
              <span class="viewer-angle-pill" id="preview-angle-pill">Angle: ${firstAngle}</span>
              ${hasQueryPhoto ? `
                <button class="viewer-toggle-btn" id="btn-toggle-split" onclick="toggleComparisonSplit('${firstImage}', '${queryPreviewSrc}')">
                  ⚡ Side-by-Side Compare
                </button>
              ` : ''}
            </div>

            <!-- Multi-Angle Thumbnails Strip -->
            ${referenceImages.length > 1 ? `
              <div class="preview-thumb-container">
                <span class="thumb-section-label">Multi-Angle Reference Photos (${referenceImages.length})</span>
                <div class="preview-thumbnails-strip" id="preview-thumb-strip">
                  ${referenceImages.map((img, idx) => `
                    <button class="preview-thumb-btn ${idx === 0 ? 'active' : ''}" 
                            onclick="selectPreviewAngle('${getImageUrl(img.image_path)}', '${img.angle}', this)"
                            title="View ${img.angle} angle">
                      <img src="${getImageUrl(img.image_path)}" alt="${img.angle}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
                      <span class="preview-thumb-tag">${img.angle}</span>
                    </button>
                  `).join("")}
                </div>
              </div>
            ` : ''}
          </div>

          <!-- Right Column: Details & Specs -->
          <div class="preview-info-col">
            ${matchBannerHtml}

            <!-- WAREHOUSE SHELF LOCATION CARD -->
            <div class="warehouse-locator-card">
              <div class="locator-card-header">
                <div class="locator-header-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  <span class="card-label">Company Shelf Location</span>
                </div>
                <span class="locator-status-badge">${design.production_status || "Active Sample Room"}</span>
              </div>

              <div class="shelf-coordinate-display">
                <div class="shelf-icon-box">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/></svg>
                </div>
                <div class="shelf-text-wrap">
                  <div class="shelf-main-location mono" id="display-shelf-text">${design.shelf_location || "Warehouse A - Rack 03 - Shelf B-02"}</div>
                  <div class="shelf-sub-desc">Physical shelf coordinate in inventory system</div>
                </div>
              </div>

              <div class="shelf-actions-bar">
                <button class="btn btn-tertiary btn-sm" onclick="toggleShelfEditForm('${design.design_id}')">
                  ✏️ Edit Shelf
                </button>
                <button class="btn btn-tertiary btn-sm" onclick="printSampleTicket('${design.design_id}', '${design.name}', '${design.shelf_location}')">
                  🖨️ Print Tag
                </button>
              </div>

              <!-- Inline Shelf Edit Form (Hidden by default) -->
              <div class="shelf-edit-form" id="shelf-edit-form" style="display: none;">
                <label class="edit-label">Update Warehouse Shelf Coordinates:</label>
                <input type="text" id="input-shelf-location" value="${design.shelf_location || ''}" placeholder="e.g. Building B - Rack C-04 - Shelf 2">
                <div class="shelf-edit-actions">
                  <button type="button" class="btn btn-secondary btn-sm" onclick="toggleShelfEditForm('${design.design_id}')">Cancel</button>
                  <button type="button" class="btn btn-primary btn-sm" onclick="saveShelfLocation('${design.design_id}')">Save Location</button>
                </div>
              </div>
            </div>

            <!-- Factory Technical Specifications -->
            <div class="factory-specs-card">
              <div class="specs-section-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
                <span class="card-label">Manufacturing & Technical Specs</span>
              </div>

              <div class="specs-grid">
                <div class="spec-item">
                  <span class="spec-label">SKU / ID</span>
                  <span class="spec-val mono">${design.design_id}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">Category</span>
                  <span class="spec-val">${design.category}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">Materials</span>
                  <span class="spec-val">${design.materials || "Leather / Rubber Sole"}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">Collection Season</span>
                  <span class="spec-val">${design.season || "Collection 2026"}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">Created By</span>
                  <span class="spec-val">${design.created_by || "Design Team"}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">Registered Date</span>
                  <span class="spec-val mono">${design.created_at || "Recent"}</span>
                </div>
              </div>

              ${design.description ? `
                <div class="spec-description-box">
                  <span class="spec-label">Design Description</span>
                  <p class="spec-desc-text">${design.description}</p>
                </div>
              ` : ''}
            </div>

            <!-- Modal Footer Actions -->
            <div class="preview-modal-footer">
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('detail-modal').style.display = 'none'">
                Close Preview
              </button>
              <button class="btn btn-danger btn-sm" onclick="deleteDesign('${design.design_id}')">
                Delete Design
              </button>
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      console.error(`Error loading design ${designId}:`, err);
      if (skuBadge) skuBadge.textContent = `SKU: ${designId} • Error`;
      detailModalBody.innerHTML = `
        <div class="modal-error-state">
          <div class="error-icon-circle">⚠️</div>
          <h4>Unable to Load Design Details</h4>
          <p>Could not retrieve specifications for SKU <strong>${designId}</strong>. (${err.message})</p>
          <div style="display: flex; gap: 10px; margin-top: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="openShoeInspectionModal('${designId}', null)">
              🔄 Retry
            </button>
            <button class="btn btn-primary btn-sm" onclick="document.getElementById('detail-modal').style.display = 'none'">
              Close
            </button>
          </div>
        </div>
      `;
      showToast(err.message, "error");
    }
  }

  // Bind to global window for inline onclick handlers
  window.openShoeInspectionModal = openShoeInspectionModal;
  window.closeShoeInspectionModal = function() {
    const modal = document.getElementById("detail-modal");
    if (modal) modal.style.display = "none";
  };

  // Switch active photo in preview modal
  window.selectPreviewAngle = function(imgPath, angle, btnEl) {
    const stage = document.getElementById("preview-stage-box");
    const queryPreviewSrc = (elements.queryPreviewImg && elements.queryPreviewImg.src && elements.queryPreviewImg.src.length > 5) ? elements.queryPreviewImg.src : null;
    const hasQuery = Boolean(state.selectedQueryFile && queryPreviewSrc);
    if (stage) {
      stage.innerHTML = `
        <img id="preview-active-image" src="${imgPath}" alt="${angle}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
        <span class="viewer-angle-pill" id="preview-angle-pill">Angle: ${angle}</span>
        ${hasQuery ? `
          <button class="viewer-toggle-btn" id="btn-toggle-split" onclick="toggleComparisonSplit('${imgPath}', '${queryPreviewSrc}')">
            ⚡ Side-by-Side Compare
          </button>
        ` : ''}
      `;
    }

    if (btnEl && btnEl.parentElement) {
      btnEl.parentElement.querySelectorAll(".preview-thumb-btn").forEach(b => b.classList.remove("active"));
      btnEl.classList.add("active");
    }
  };

  // Side-by-side comparison toggle
  window.toggleComparisonSplit = function(catalogImgSrc, queryImgSrc) {
    const stage = document.getElementById("preview-stage-box");
    if (!stage) return;

    if (stage.querySelector(".split-view-container")) {
      // Revert to single view
      stage.innerHTML = `
        <img id="preview-active-image" src="${catalogImgSrc}" alt="Catalog Reference" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
        <span class="viewer-angle-pill">Single View</span>
        <button class="viewer-toggle-btn" onclick="toggleComparisonSplit('${catalogImgSrc}', '${queryImgSrc}')">
          ⚡ Side-by-Side Compare
        </button>
      `;
    } else {
      // Switch to split view
      stage.innerHTML = `
        <div class="split-view-container">
          <div class="split-box">
            <img src="${queryImgSrc}" alt="Query Target" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
            <span class="split-label">Target Query Photo</span>
          </div>
          <div class="split-box">
            <img src="${catalogImgSrc}" alt="Catalog Match" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'1.5\'><path d=\'M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z\'/><path d=\'M16 8l-4 4\'/></svg>';">
            <span class="split-label">Catalog Reference</span>
          </div>
        </div>
        <button class="viewer-toggle-btn" onclick="toggleComparisonSplit('${catalogImgSrc}', '${queryImgSrc}')">
          🔍 Single View
        </button>
      `;
    }
  };

  // Toggle shelf location edit form
  window.toggleShelfEditForm = function(designId) {
    const form = document.getElementById("shelf-edit-form");
    if (form) {
      form.style.display = form.style.display === "none" ? "flex" : "none";
    }
  };

  // Save new shelf location via API
  window.saveShelfLocation = async function(designId) {
    const input = document.getElementById("input-shelf-location");
    if (!input) return;
    const newLocation = input.value.trim();
    if (!newLocation) {
      showToast("Please enter a valid shelf location", "error");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("shelf_location", newLocation);

      const res = await fetch(getApiUrl(`/api/designs/${designId}/location`), {
        method: "PUT",
        body: formData
      });

      if (res.ok) {
        showToast(`Shelf location updated to: ${newLocation}`, "success");
        const display = document.getElementById("display-shelf-text");
        if (display) display.textContent = newLocation;
        toggleShelfEditForm(designId);
        await fetchCatalog();
      } else {
        throw new Error("Failed to update shelf location");
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Print sample ticket
  window.printSampleTicket = function(designId, name, shelf) {
    const printWin = window.open('', '', 'width=600,height=400');
    printWin.document.write(`
      <html>
        <head>
          <title>Shelf Tag - ${designId}</title>
          <style>
            body { font-family: sans-serif; padding: 24px; text-align: center; border: 2px dashed #000; }
            h2 { margin: 0 0 8px 0; font-size: 22px; }
            .sku { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 12px; }
            .shelf { font-size: 20px; font-weight: bold; background: #eee; padding: 10px; border-radius: 4px; display: inline-block; margin: 12px 0; }
            .footer { font-size: 12px; color: #666; margin-top: 16px; }
          </style>
        </head>
        <body>
          <h2>ShoeMatch Factory Shelf Tag</h2>
          <div class="sku">SKU: ${designId} &bull; ${name}</div>
          <div class="shelf">📍 ${shelf || 'Warehouse Location'}</div>
          <div class="footer">Printed on ${new Date().toLocaleString()} &bull; ShoeMatch AI Pro</div>
        </body>
      </html>
    `);
    printWin.document.close();
    printWin.focus();
    printWin.print();
    printWin.close();
  };

  window.deleteDesign = async function(designId) {
    if (!confirm(`Are you sure you want to delete ${designId}? This will re-index the catalog.`)) return;

    try {
      const res = await fetch(getApiUrl(`/api/designs/${designId}`), { method: "DELETE" });
      if (res.ok) {
        showToast(`Design ${designId} deleted successfully`, "success");
        elements.detailModal.style.display = "none";
        await fetchCatalog();
        await fetchStats();
      } else {
        throw new Error("Failed to delete design");
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Preset Templates
  const DESIGN_TEMPLATES = {
    monk_loafer: {
      name: "Monk Strap Heritage Loafer",
      category: "Slip-On Loafer",
      shelf: "Building A - Section 1 - Rack B-01 - Shelf 1",
      status: "Master Craftsman Vault",
      materials: "Full Grain Crust Calfskin / Brass Hardware / Leather Sole",
      season: "Autumn/Winter 2026",
      desc: "Luxury single monk strap loafer with handcrafted burnish and Blake stitched sole."
    },
    pro_runner: {
      name: "AeroGlide Pro Marathon Racer",
      category: "Running Shoe",
      shelf: "Building A - Section 4 - Rack A-08 - Shelf 1",
      status: "Production Line Floor",
      materials: "Engineered Monofilament Mesh / Carbon Fiber Plate / Zoom TPU",
      season: "Spring/Summer 2026",
      desc: "High-performance racing flat with carbon plate propulsion and responsive foam midsole."
    },
    brogue_oxford: {
      name: "Sovereign Wingtip Brogue",
      category: "Classic Oxford",
      shelf: "Building A - Section 1 - Rack B-01 - Shelf 3",
      status: "Active Sample Room",
      materials: "Scotch Grain Leather / Goodyear Welted Oak Sole",
      season: "Heritage Collection 2026",
      desc: "Classic full brogue oxford with hand-punched medallion toe and double leather sole."
    },
    trail_boot: {
      name: "Apex Ridge All-Terrain Boot",
      category: "Hiking Boot",
      shelf: "Building B - Section 2 - Rack E-01 - Shelf 4",
      status: "QC Archive",
      materials: "Waterproof Oiled Nubuck / Vibram Megagrip Rubber / Gore-Tex Lining",
      season: "Winter 2026",
      desc: "Rugged high-traction outdoor boot engineered for alpine expeditions and heavy weather."
    },
    minimal_trainer: {
      name: "Studio Clean Low-Top Trainer",
      category: "Sneaker",
      shelf: "Building A - Section 1 - Rack A-03 - Shelf 4",
      status: "Active Sample Room",
      materials: "Italian White Nappa Leather / Margom Cupsole",
      season: "Core Collection 2026",
      desc: "Minimalist silhouette featuring calfskin lining and stitched rubber cupsole."
    },
    cloud_slide: {
      name: "Comfort Cloud Slide Sandal",
      category: "Slide Sandal",
      shelf: "Warehouse B - Rack 01 - Shelf S-01",
      status: "Active Sample Room",
      materials: "Hydrophobic EVA Foam / Anti-Slip Contoured Footbed",
      season: "Summer 2026",
      desc: "Ultra-cushioned open-toe recovery slide designed for maximum comfort."
    },
    breeze_flipflop: {
      name: "Breeze Ergonomic Flip-Flop",
      category: "Flip-Flop",
      shelf: "Warehouse B - Rack 01 - Shelf S-02",
      status: "Active Sample Room",
      materials: "Natural Gum Rubber / Soft Woven Strap / Arch Support",
      season: "Summer 2026",
      desc: "Lightweight dual-density ergonomic flip-flop with textured grip footbed."
    },
    cozy_slipper: {
      name: "Cozy Velvet Bedroom Slipper",
      category: "House Slipper",
      shelf: "Warehouse B - Rack 02 - Shelf S-03",
      status: "Active Sample Room",
      materials: "Plush Velvet / Memory Foam Cushion / Non-Marking TPR Sole",
      season: "Winter 2026",
      desc: "Warm memory foam indoor slipper with fleece lining and quiet indoor sole."
    },
    urban_mule: {
      name: "Urban Suede Mule Slide",
      category: "Mule Slipper",
      shelf: "Warehouse B - Rack 02 - Shelf S-04",
      status: "Active Sample Room",
      materials: "Perforated Suede / Natural Cork Footbed / Rubber Outsole",
      season: "Collection 2026",
      desc: "Open-back slip-on mule slide with breathable suede upper and orthopedic cork sole."
    }
  };

  window.applyDesignTemplate = function(key) {
    if (!key || !DESIGN_TEMPLATES[key]) return;
    const tpl = DESIGN_TEMPLATES[key];

    const randomNum = Math.floor(Math.random() * 800) + 100;
    const prefix = (tpl.category === "Slide Sandal" || tpl.category === "Flip-Flop" || tpl.category === "House Slipper" || tpl.category === "Mule Slipper") ? "SLIP" : "SHOE";
    const idInput = document.getElementById("new-design-id");
    const nameInput = document.getElementById("new-design-name");
    const catInput = document.getElementById("new-design-category");
    const shelfInput = document.getElementById("new-design-shelf");
    const statusInput = document.getElementById("new-design-status");
    const matInput = document.getElementById("new-design-materials");
    const seasonInput = document.getElementById("new-design-season");
    const descInput = document.getElementById("new-design-desc");

    if (idInput) idInput.value = `${prefix}-${randomNum}`;
    if (nameInput) nameInput.value = tpl.name;
    if (catInput) catInput.value = tpl.category;
    if (shelfInput) shelfInput.value = tpl.shelf;
    if (statusInput) statusInput.value = tpl.status;
    if (matInput) matInput.value = tpl.materials;
    if (seasonInput) seasonInput.value = tpl.season;
    if (descInput) descInput.value = tpl.desc;

    showToast(`Template '${tpl.name}' applied!`, "info");
  };

  // ==========================================
  // Add New Design Modal (Incremental Ingestion)
  // ==========================================
  function openAddModal() {
    state.modalFiles = [];
    elements.modalPreviews.innerHTML = "";
    elements.addDesignForm.reset();
    if (document.getElementById("template-selector")) {
      document.getElementById("template-selector").value = "";
    }
    // Auto-generate next design SKU
    const nextIdx = state.catalog.length + 1;
    document.getElementById("new-design-id").value = `SHOE-${String(nextIdx).padStart(3, "0")}`;
    elements.addModal.style.display = "flex";
  }

  function closeAddModal() {
    elements.addModal.style.display = "none";
  }

  function handleModalFilesSelect(e) {
    if (e.target.files) {
      Array.from(e.target.files).forEach(f => {
        if (f.type.startsWith("image/")) state.modalFiles.push(f);
      });
      renderModalPreviews();
    }
  }

  function renderModalPreviews() {
    elements.modalPreviews.innerHTML = "";
    const angleLabels = ["Side", "Top", "Sole", "3/4", "Heel", "Detail"];
    state.modalFiles.forEach((file, idx) => {
      const div = document.createElement("div");
      div.className = "modal-preview-item";
      const angle = angleLabels[idx % angleLabels.length];
      div.innerHTML = `
        <img src="${URL.createObjectURL(file)}" alt="Preview">
        <span style="position: absolute; bottom: 2px; left: 2px; font-size: 0.65rem; background: rgba(0,0,0,0.85); color: #fff; padding: 1px 4px; border-radius: 2px;">${angle}</span>
        <button type="button" onclick="removeModalFile(${idx})" style="position: absolute; top: 2px; right: 2px; background: rgba(239,68,68,0.9); border: none; color: #fff; border-radius: 50%; width: 18px; height: 18px; font-size: 11px; cursor: pointer; display: flex; align-items: center; justify-content: center;">&times;</button>
      `;
      elements.modalPreviews.appendChild(div);
    });
  }

  window.removeModalFile = function(idx) {
    state.modalFiles.splice(idx, 1);
    renderModalPreviews();
  };

  async function submitNewDesign(e) {
    e.preventDefault();
    if (state.modalFiles.length === 0) {
      showToast("Please select at least one reference image", "error");
      return;
    }

    const designId = document.getElementById("new-design-id").value.trim();
    const name = document.getElementById("new-design-name").value.trim();
    const category = document.getElementById("new-design-category").value;
    const creator = document.getElementById("new-design-creator").value.trim();
    const shelf = document.getElementById("new-design-shelf") ? document.getElementById("new-design-shelf").value.trim() : "Warehouse A - Rack 03 - Shelf B-02";
    const status = document.getElementById("new-design-status") ? document.getElementById("new-design-status").value : "Active Sample Room";
    const materials = document.getElementById("new-design-materials") ? document.getElementById("new-design-materials").value.trim() : "Full Grain Leather / Rubber Sole";
    const season = document.getElementById("new-design-season") ? document.getElementById("new-design-season").value.trim() : "Collection 2026";
    const desc = document.getElementById("new-design-desc").value.trim();

    const formData = new FormData();
    formData.append("design_id", designId);
    formData.append("name", name);
    formData.append("category", category);
    formData.append("created_by", creator);
    formData.append("shelf_location", shelf);
    formData.append("production_status", status);
    formData.append("materials", materials);
    formData.append("season", season);
    formData.append("description", desc);

    state.modalFiles.forEach(f => {
      formData.append("files", f);
    });

    const submitBtn = document.getElementById("btn-submit-add");
    submitBtn.disabled = true;
    submitBtn.querySelector("span").textContent = "Indexing (Incremental Add)...";

    try {
      const res = await fetch(getApiUrl("/api/designs"), {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to add design");
      }

      showToast(`Design '${name}' successfully indexed!`, "success");
      closeAddModal();
      await fetchCatalog();
      await fetchStats();
      switchTab("catalog-tab");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.querySelector("span").textContent = "Index Design (Incremental Add)";
    }
  }

  // ==========================================
  // Audit Logs & Pagination
  // ==========================================
  state.logsCurrentPage = 1;
  state.logsPerPage = 10;

  window.handleLogsPerPageChange = function(val) {
    state.logsPerPage = parseInt(val, 10) || 10;
    state.logsCurrentPage = 1;
    renderLogsTable(state.logs);
  };

  window.changeLogsPage = function(delta) {
    const totalPages = Math.ceil((state.logs || []).length / state.logsPerPage) || 1;
    const target = state.logsCurrentPage + delta;
    if (target >= 1 && target <= totalPages) {
      state.logsCurrentPage = target;
      renderLogsTable(state.logs);
    }
  };

  window.getLogThumbnailUrl = function(path) {
    if (!path || path === "memory_query.jpg" || path === "none" || path === "undefined") {
      return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='1.5'><path d='M20.24 12.24a6 6 0 0 0-8.49-8.49L3.5 12.00a6 6 0 0 0 8.49 8.49l8.25-8.25z'/><path d='M16 8l-4 4'/></svg>";
    }
    return getImageUrl(path);
  };

  async function fetchLogs() {
    try {
      const res = await window.authenticatedFetch(getApiUrl("/api/logs?limit=200"));
      if (res.ok) {
        const data = await res.json();
        state.logs = data.logs || [];
        renderLogsTable(state.logs);
      }
    } catch (err) {
      console.error("Failed to fetch logs:", err);
    }
  }
  window.fetchLogs = fetchLogs;

  function renderLogsTable(logs) {
    if (!elements.logsTbody) return;
    elements.logsTbody.innerHTML = "";

    if (!logs || logs.length === 0) {
      elements.logsTbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No queries logged yet. Run a match in the Studio to generate logs.
          </td>
        </tr>
      `;
      const infoEl = document.getElementById("logs-pagination-info");
      if (infoEl) infoEl.textContent = "Showing 0 of 0 entries";
      return;
    }

    const totalLogs = logs.length;
    const totalPages = Math.ceil(totalLogs / state.logsPerPage) || 1;
    state.logsCurrentPage = Math.min(state.logsCurrentPage, totalPages);

    const startIdx = (state.logsCurrentPage - 1) * state.logsPerPage;
    const pageLogs = logs.slice(startIdx, startIdx + state.logsPerPage);

    // Update pagination info & controls
    const infoEl = document.getElementById("logs-pagination-info");
    if (infoEl) {
      const endIdx = Math.min(startIdx + state.logsPerPage, totalLogs);
      infoEl.textContent = `Showing ${startIdx + 1}-${endIdx} of ${totalLogs} entries (Page ${state.logsCurrentPage} of ${totalPages})`;
    }
    const prevBtn = document.getElementById("btn-logs-prev");
    const nextBtn = document.getElementById("btn-logs-next");
    if (prevBtn) prevBtn.disabled = (state.logsCurrentPage <= 1);
    if (nextBtn) nextBtn.disabled = (state.logsCurrentPage >= totalPages);

    const fallbackSvg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='1.5'><rect x='3' y='3' width='18' height='18' rx='2'/><path d='M8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z'/><path d='M21 15l-5-5L5 21'/></svg>";

    pageLogs.forEach(log => {
      const tr = document.createElement("tr");

      const conf = log.confidence_pct != null ? parseFloat(log.confidence_pct) : 0;
      const color = (conf >= 85) ? "high" : (conf >= 70) ? "moderate" : "low";
      const cat = (log.detected_category || "shoe").toLowerCase();
      
      const isNone = (cat === "none");
      const isSlipper = (cat === "slipper");
      const catBadge = isNone ? '<span style="color: var(--status-danger-text); font-weight: 700; font-size: 0.78rem;">🚫 None</span>' :
                       (isSlipper ? '<span style="color: #60a5fa; font-weight: 700; font-size: 0.78rem;">🩴 Slipper</span>' : '<span style="color: var(--status-success-text); font-weight: 700; font-size: 0.78rem;">👟 Shoe</span>');

      let statusBadgeHtml = '<span class="log-status-badge success">✓ Success</span>';
      if (isSlipper) {
        statusBadgeHtml = '<span class="log-status-badge warning">🩴 Slipper Rej</span>';
      } else if (isNone) {
        statusBadgeHtml = '<span class="log-status-badge danger">🚫 No Object</span>';
      } else if (conf < 70) {
        statusBadgeHtml = '<span class="log-status-badge warning">⚠️ Low Match</span>';
      }

      const matchName = log.top_match_name || "No Match";
      const matchId = log.top_match_id || "--";
      const latencyStr = log.latency_ms ? `${Math.round(log.latency_ms)} ms` : "-- ms";
      const imgSrc = window.getLogThumbnailUrl(log.query_image_path);

      tr.innerHTML = `
        <td style="text-align: center; width: 64px;">
          <div class="log-thumb-frame">
            <img src="${imgSrc}" class="log-thumb" alt="Query Thumbnail" onerror="this.onerror=null; this.src='${fallbackSvg}';">
          </div>
        </td>
        <td style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-secondary); white-space: nowrap;">${log.created_at || 'Recently'}</td>
        <td>${catBadge}</td>
        <td>
          <div style="font-weight: 700; color: var(--text-primary); font-size: 0.85rem;">${matchName}</div>
          <div style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--text-muted);">${matchId}</div>
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="preview-match-pill ${color}">${conf}%</span>
          </div>
        </td>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary); white-space: nowrap;">${latencyStr}</td>
        <td>${statusBadgeHtml}</td>
      `;

      elements.logsTbody.appendChild(tr);
    });
  }

  window.reMatchFromLog = async function(imageUrl) {
    try {
      const res = await fetch(imageUrl);
      const blob = await res.blob();
      const file = new File([blob], "log_query.jpg", { type: "image/jpeg" });
      setQueryFile(file);
      switchTab("match-tab");
      setTimeout(() => executeVisualMatch(), 200);
    } catch (err) {
      showToast("Could not load image from log", "error");
    }
  };

  // ==========================================
  // Live Camera & Native Capture Handling
  // ==========================================
  async function handleCameraClick(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    // Check for native Capacitor mobile camera plugin first
    if (window.Capacitor && window.Capacitor.isNativePlatform() && window.Capacitor.Plugins && window.Capacitor.Plugins.Camera) {
      try {
        const camera = window.Capacitor.Plugins.Camera;
        const image = await camera.getPhoto({
          quality: 90,
          allowEditing: false,
          resultType: 'uri',
          source: 'CAMERA'
        });
        if (image && image.webPath) {
          const res = await fetch(image.webPath);
          const blob = await res.blob();
          const file = new File([blob], `camera_photo_${Date.now()}.jpg`, { type: 'image/jpeg' });
          setQueryFile(file);
          showToast("Photo captured from native camera shutter!", "success");
          return;
        }
      } catch (err) {
        console.warn("Native Capacitor camera cancelled or error:", err);
      }
    }

    const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
    
    // On mobile devices, opening native hardware camera shutter provides 4K quality and autofocus
    if (isMobile && elements.cameraNativeInput) {
      elements.cameraNativeInput.click();
      return;
    }

    // On desktop / laptops, launch the interactive live viewfinder modal
    openCameraModal();
  }

  async function openCameraModal() {
    if (elements.cameraModal) elements.cameraModal.style.display = "flex";
    if (elements.cameraLoadingNotice) elements.cameraLoadingNotice.style.display = "block";
    if (elements.cameraFeedContainer) elements.cameraFeedContainer.style.display = "flex";
    if (elements.cameraErrorContainer) elements.cameraErrorContainer.style.display = "none";
    if (elements.btnSnapPhoto) elements.btnSnapPhoto.style.display = "inline-flex";

    // If WebRTC is unsupported or restricted by origin policy, show direct shutter trigger
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showCameraError("Live webcam streaming is not supported on this browser/origin.");
      return;
    }

    await startCameraStream();
  }

  async function startCameraStream() {
    if (state.cameraStream) {
      try {
        state.cameraStream.getTracks().forEach(track => track.stop());
      } catch (e) {}
      state.cameraStream = null;
    }

    try {
      let stream;
      try {
        // Try ideal facingMode first
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: state.cameraFacingMode } },
          audio: false
        });
      } catch (initialErr) {
        console.warn("Retrying with simple video constraints:", initialErr);
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }

      state.cameraStream = stream;
      if (elements.cameraVideo) {
        elements.cameraVideo.srcObject = stream;
        elements.cameraVideo.setAttribute("playsinline", "true");
        elements.cameraVideo.setAttribute("autoplay", "true");
        elements.cameraVideo.muted = true;
        await elements.cameraVideo.play();
      }
      if (elements.cameraLoadingNotice) elements.cameraLoadingNotice.style.display = "none";

      // Show switch camera button if multiple cameras exist
      if (navigator.mediaDevices.enumerateDevices && elements.btnSwitchCamera) {
        try {
          const devices = await navigator.mediaDevices.enumerateDevices();
          const videoDevices = devices.filter(d => d.kind === "videoinput");
          elements.btnSwitchCamera.style.display = (videoDevices.length > 1) ? "inline-flex" : "none";
        } catch (e) {
          elements.btnSwitchCamera.style.display = "none";
        }
      }
    } catch (err) {
      console.error("Camera access error:", err);
      showCameraError("Camera permission denied or camera device not found.");
    }
  }

  function showCameraError(msg) {
    if (elements.cameraLoadingNotice) elements.cameraLoadingNotice.style.display = "none";
    if (elements.cameraFeedContainer) elements.cameraFeedContainer.style.display = "none";
    if (elements.cameraErrorContainer) {
      elements.cameraErrorContainer.style.display = "block";
      if (elements.cameraErrorMessage) elements.cameraErrorMessage.textContent = msg;
    }
    if (elements.btnSnapPhoto) elements.btnSnapPhoto.style.display = "none";
    if (elements.btnSwitchCamera) elements.btnSwitchCamera.style.display = "none";
  }

  function closeCameraModal() {
    if (state.cameraStream) {
      try {
        state.cameraStream.getTracks().forEach(track => track.stop());
      } catch (e) {}
      state.cameraStream = null;
    }
    if (elements.cameraVideo) {
      elements.cameraVideo.srcObject = null;
    }
    if (elements.cameraModal) {
      elements.cameraModal.style.display = "none";
    }
  }

  async function switchCamera() {
    state.cameraFacingMode = (state.cameraFacingMode === "environment") ? "user" : "environment";
    await startCameraStream();
  }

  function snapPhotoFromCamera() {
    if (!elements.cameraVideo || !state.cameraStream) {
      showToast("Camera stream not ready.", "warning");
      return;
    }

    const video = elements.cameraVideo;
    const canvas = elements.cameraCanvas || document.createElement("canvas");
    const width = video.videoWidth || video.clientWidth || 640;
    const height = video.videoHeight || video.clientHeight || 480;

    if (width === 0 || height === 0) {
      showToast("Camera feed is warming up. Please try snapping again in a moment.", "warning");
      return;
    }

    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, width, height);

    canvas.toBlob((blob) => {
      if (!blob) {
        showToast("Failed to capture image snapshot.", "error");
        return;
      }
      const file = new File([blob], `camera_snap_${Date.now()}.jpg`, { type: "image/jpeg" });
      closeCameraModal();
      setQueryFile(file);
      showToast("Photo captured from camera!", "success");
    }, "image/jpeg", 0.92);
  }

  // ==========================================
  // Toast Notifications
  // ==========================================
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // ==========================================================================
  // Location Hierarchy & Warehouse Management
  // ==========================================================================
  state.locationsViewMode = localStorage.getItem("shoematch_locations_view") || "tree";
  state.locationsSearchQuery = "";
  state.locationsZoneFilter = "";
  state.locationsOccupancyFilter = "";
  state.locationHierarchy = [];

  window.setLocationsViewMode = function(mode) {
    state.locationsViewMode = mode;
    try { localStorage.setItem("shoematch_locations_view", mode); } catch (e) {}
    
    const treeBtn = document.getElementById("btn-loc-view-tree");
    const tableBtn = document.getElementById("btn-loc-view-table");
    const treeWrap = document.getElementById("loc-tree-container");
    const tableWrap = document.getElementById("loc-table-container");

    if (mode === "table") {
      if (treeBtn) treeBtn.classList.remove("active");
      if (tableBtn) tableBtn.classList.add("active");
      if (treeWrap) treeWrap.style.display = "none";
      if (tableWrap) tableWrap.style.display = "block";
      fetchSlotsTable();
    } else {
      if (treeBtn) treeBtn.classList.add("active");
      if (tableBtn) tableBtn.classList.remove("active");
      if (treeWrap) treeWrap.style.display = "block";
      if (tableWrap) tableWrap.style.display = "none";
      renderLocationHierarchy();
    }
  };

  async function fetchLocationHierarchy() {
    try {
      const res = await window.authenticatedFetch(getApiUrl("/api/locations/hierarchy"));
      if (res.ok) {
        const data = await res.json();
        state.locationHierarchy = data.hierarchy || [];
        
        // Populate Zone Filter Select
        const zoneFilter = document.getElementById("loc-zone-filter");
        if (zoneFilter) {
          const currentVal = zoneFilter.value;
          zoneFilter.innerHTML = '<option value="">All Zones / Shoe Matches</option>';
          state.locationHierarchy.forEach(sm => {
            const opt = document.createElement("option");
            opt.value = sm.id;
            opt.textContent = sm.name;
            zoneFilter.appendChild(opt);
          });
          zoneFilter.value = currentVal;
        }

        if (state.locationsViewMode === "table") {
          fetchSlotsTable();
        } else {
          renderLocationHierarchy();
        }
      }
    } catch (err) {
      console.error("Failed to fetch location hierarchy:", err);
    }
  }

  window.escapeHtml = function(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  window.highlightKeyword = function(text, keyword) {
    if (text === null || text === undefined) return "";
    const str = String(text);
    if (!keyword || !keyword.trim()) return window.escapeHtml(str);

    const q = keyword.trim().toLowerCase();
    const lower = str.toLowerCase();
    let result = "";
    let curr = 0;
    let idx = lower.indexOf(q, curr);

    if (idx === -1) return window.escapeHtml(str);

    while (idx !== -1) {
      result += window.escapeHtml(str.substring(curr, idx));
      const matchText = str.substring(idx, idx + q.length);
      result += `<mark class="search-highlight">${window.escapeHtml(matchText)}</mark>`;
      curr = idx + q.length;
      idx = lower.indexOf(q, curr);
    }
    result += window.escapeHtml(str.substring(curr));
    return result;
  };

  window.calculateLocationRelevanceScore = function(slot, query) {
    if (!query || !query.trim()) return 1;
    const q = query.trim().toLowerCase();

    const slotName = (slot.slot_name || slot.name || "").toLowerCase();
    const designId = (slot.assigned_design_id || "").toLowerCase();
    const designName = (slot.design_name || "").toLowerCase();
    
    const zoneName = (slot.shoe_match_name || slot.zone_name || slot.sm_name || "").toLowerCase();
    const shelfName = (slot.shelf_name || "").toLowerCase();
    const drawerName = (slot.drawer_name || "").toLowerCase();
    const category = (slot.design_category || "").toLowerCase();

    let maxScore = 0;

    // Exact Match on primary identifier (100 pts)
    if (slotName === q || designId === q || designName === q) {
      maxScore = Math.max(maxScore, 100);
    }
    // Prefix Match on primary identifier (80 pts)
    else if (slotName.startsWith(q) || designId.startsWith(q) || designName.startsWith(q)) {
      maxScore = Math.max(maxScore, 80);
    }
    // Substring Match on primary identifier (60 pts)
    else if (slotName.includes(q) || designId.includes(q) || designName.includes(q)) {
      maxScore = Math.max(maxScore, 60);
    }

    // Exact Match on secondary hierarchy fields (50 pts)
    if (zoneName === q || shelfName === q || drawerName === q || category === q) {
      maxScore = Math.max(maxScore, 50);
    }
    // Prefix Match on secondary hierarchy fields (40 pts)
    else if (zoneName.startsWith(q) || shelfName.startsWith(q) || drawerName.startsWith(q) || category.startsWith(q)) {
      maxScore = Math.max(maxScore, 40);
    }
    // Substring Match on secondary hierarchy fields (30 pts)
    else if (zoneName.includes(q) || shelfName.includes(q) || drawerName.includes(q) || category.includes(q)) {
      maxScore = Math.max(maxScore, 30);
    }

    return maxScore;
  };

  function renderLocationHierarchy() {
    const treeWrap = document.getElementById("loc-tree-container");
    if (!treeWrap) return;
    treeWrap.innerHTML = "";

    const searchQuery = (state.locationsSearchQuery || "").trim();
    const zoneId = state.locationsZoneFilter ? parseInt(state.locationsZoneFilter, 10) : null;
    const occupancy = state.locationsOccupancyFilter;

    let filteredHierarchy = state.locationHierarchy || [];
    if (zoneId) {
      filteredHierarchy = filteredHierarchy.filter(sm => sm.id === zoneId);
    }

    if (!filteredHierarchy || filteredHierarchy.length === 0) {
      treeWrap.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-muted);">
          <h4>No Location Hierarchy Found</h4>
          <p>Click "Add Location Node" to create zones, shelves, drawers, and slots.</p>
        </div>
      `;
      return;
    }

    let renderedAnyNode = false;

    filteredHierarchy.forEach(sm => {
      const smNameMatch = searchQuery && sm.name.toLowerCase().includes(searchQuery.toLowerCase());
      const shelvesToRender = [];

      (sm.shelves || []).forEach(sh => {
        const shNameMatch = searchQuery && sh.name.toLowerCase().includes(searchQuery.toLowerCase());
        const drawersToRender = [];

        (sh.drawers || []).forEach(dr => {
          const drNameMatch = searchQuery && dr.name.toLowerCase().includes(searchQuery.toLowerCase());

          // Gather and score slots in this drawer
          let slotsInDrawer = (dr.slots || []).map(s => {
            const slotObj = {
              ...s,
              shoe_match_name: sm.name,
              shelf_name: sh.name,
              drawer_name: dr.name
            };
            const score = window.calculateLocationRelevanceScore(slotObj, searchQuery);
            const effectiveScore = (smNameMatch || shNameMatch || drNameMatch) ? Math.max(score, 30) : score;
            return { ...slotObj, score: effectiveScore };
          });

          // Occupancy filter & Search score filter
          slotsInDrawer = slotsInDrawer.filter(s => {
            const matchesOccupancy = !occupancy || 
              (occupancy === "occupied" && s.is_occupied) || 
              (occupancy === "vacant" && !s.is_occupied);
            return matchesOccupancy && (searchQuery ? s.score > 0 : true);
          });

          // Relevance Sort slots within drawer
          if (searchQuery) {
            slotsInDrawer.sort((a, b) => b.score - a.score);
          }

          if (slotsInDrawer.length > 0 || (searchQuery && drNameMatch)) {
            drawersToRender.push({ drawer: dr, slots: slotsInDrawer });
          }
        });

        if (drawersToRender.length > 0 || (searchQuery && shNameMatch)) {
          shelvesToRender.push({ shelf: sh, drawers: drawersToRender });
        }
      });

      if (shelvesToRender.length === 0 && !smNameMatch && searchQuery) {
        return;
      }

      renderedAnyNode = true;

      const smDetails = document.createElement("details");
      smDetails.className = "loc-tree-node";
      smDetails.open = true;

      const totalSlots = (sm.shelves || []).reduce((acc, sh) => 
        acc + (sh.drawers || []).reduce((dAcc, dr) => dAcc + (dr.slots || []).length, 0), 0);
      const occupiedSlots = (sm.shelves || []).reduce((acc, sh) => 
        acc + (sh.drawers || []).reduce((dAcc, dr) => dAcc + (dr.slots || []).filter(s => s.is_occupied).length, 0), 0);

      const hlZoneName = window.highlightKeyword(sm.name, searchQuery);

      smDetails.innerHTML = `
        <summary>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.1rem;">🏢</span>
            <span>Zone / Shoe Match: <strong>${hlZoneName}</strong></span>
            <span style="font-size: 0.75rem; font-family: var(--font-mono); color: var(--text-muted);">(${window.escapeHtml(sm.description || 'Facility Storage')})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 0.75rem; font-family: var(--font-mono); color: var(--text-secondary);">${occupiedSlots}/${totalSlots} Slots Occupied</span>
            <button class="btn btn-secondary btn-sm" onclick="event.preventDefault(); openAddLocationModal('shelf', ${sm.id});" style="font-size: 0.72rem; padding: 2px 8px;">+ Add Shelf</button>
            <button class="btn btn-danger btn-sm" onclick="event.preventDefault(); deleteLocationNode('shoe_match', ${sm.id});" style="font-size: 0.72rem; padding: 2px 8px;">Delete</button>
          </div>
        </summary>
        <div class="loc-tree-children" id="sm-children-${sm.id}"></div>
      `;

      const smChildren = smDetails.querySelector(`#sm-children-${sm.id}`);
      shelvesToRender.forEach(({ shelf: sh, drawers }) => {
        const shDetails = document.createElement("details");
        shDetails.className = "loc-tree-node";
        shDetails.open = true;
        shDetails.style.marginLeft = "12px";

        const hlShelfName = window.highlightKeyword(sh.name, searchQuery);

        shDetails.innerHTML = `
          <summary>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1rem;">📦</span>
              <span>Shelf: <strong>${hlShelfName}</strong></span>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <button class="btn btn-secondary btn-sm" onclick="event.preventDefault(); openAddLocationModal('drawer', ${sm.id}, ${sh.id});" style="font-size: 0.72rem; padding: 2px 8px;">+ Add Drawer</button>
              <button class="btn btn-danger btn-sm" onclick="event.preventDefault(); deleteLocationNode('shelf', ${sh.id});" style="font-size: 0.72rem; padding: 2px 8px;">Delete</button>
            </div>
          </summary>
          <div class="loc-tree-children" id="sh-children-${sh.id}"></div>
        `;

        const shChildren = shDetails.querySelector(`#sh-children-${sh.id}`);
        drawers.forEach(({ drawer: dr, slots }) => {
          const drDetails = document.createElement("details");
          drDetails.className = "loc-tree-node";
          drDetails.open = true;
          drDetails.style.marginLeft = "12px";

          const hlDrawerName = window.highlightKeyword(dr.name, searchQuery);

          drDetails.innerHTML = `
            <summary>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1rem;">🗄️</span>
                <span>Drawer: <strong>${hlDrawerName}</strong></span>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <button class="btn btn-secondary btn-sm" onclick="event.preventDefault(); openAddLocationModal('slot', ${sm.id}, ${sh.id}, ${dr.id});" style="font-size: 0.72rem; padding: 2px 8px;">+ Add Slot</button>
                <button class="btn btn-danger btn-sm" onclick="event.preventDefault(); deleteLocationNode('drawer', ${dr.id});" style="font-size: 0.72rem; padding: 2px 8px;">Delete</button>
              </div>
            </summary>
            <div class="loc-tree-children" id="dr-children-${dr.id}"></div>
          `;

          const drChildren = drDetails.querySelector(`#dr-children-${dr.id}`);
          slots.forEach(s => {
            const slotDiv = document.createElement("div");
            slotDiv.className = "loc-slot-item";
            
            const isOccupied = s.is_occupied === 1 && s.assigned_design_id;
            const hlDesignName = window.highlightKeyword(s.design_name || s.assigned_design_id, searchQuery);
            const hlDesignId = window.highlightKeyword(s.assigned_design_id, searchQuery);
            const hlSlotName = window.highlightKeyword(s.name, searchQuery);

            const statusPill = isOccupied ? 
              `<span class="slot-occupied-pill">Occupied: ${hlDesignName} (${hlDesignId})</span>` :
              `<span class="slot-vacant-pill">Vacant Slot</span>`;

            const fullPath = `${sm.name} > ${sh.name} > ${dr.name} > ${s.name}`;

            slotDiv.innerHTML = `
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-family: var(--font-mono); font-weight: 700; color: var(--text-primary);">📍 ${hlSlotName}</span>
                ${statusPill}
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <button class="btn btn-secondary btn-sm" onclick="openAssignLocationModal(${s.id}, '${(s.assigned_design_id || '').replace(/'/g, "\\'")}', '${fullPath.replace(/'/g, "\\'")}')" style="font-size: 0.72rem; padding: 2px 8px;">
                  ${isOccupied ? 'Reassign' : 'Assign Design'}
                </button>
                ${isOccupied ? `<button class="btn btn-secondary btn-sm" onclick="unassignLocationSlot(${s.id})" style="font-size: 0.72rem; padding: 2px 8px; color: var(--status-warning-text);">Vacate</button>` : ''}
                <button class="btn btn-danger btn-sm" onclick="deleteLocationNode('slot', ${s.id})" style="font-size: 0.72rem; padding: 2px 8px;">Delete</button>
              </div>
            `;

            drChildren.appendChild(slotDiv);
          });

          shChildren.appendChild(drDetails);
        });

        smChildren.appendChild(shDetails);
      });

      treeWrap.appendChild(smDetails);
    });

    if (!renderedAnyNode) {
      treeWrap.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-muted);">
          <h4>No Location Slots Match "${window.escapeHtml(searchQuery)}"</h4>
          <p>Try refining your search keyword or clearing filters.</p>
        </div>
      `;
    }
  }

  async function fetchSlotsTable() {
    const tbody = document.getElementById("loc-slots-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    try {
      const qParams = new URLSearchParams();
      if (state.locationsSearchQuery) qParams.set("search", state.locationsSearchQuery);
      if (state.locationsZoneFilter) qParams.set("zone_id", state.locationsZoneFilter);
      if (state.locationsOccupancyFilter) qParams.set("status", state.locationsOccupancyFilter);

      const res = await window.authenticatedFetch(getApiUrl(`/api/locations/slots?${qParams.toString()}`));
      if (res.ok) {
        const data = await res.json();
        let slots = data.slots || [];
        const searchQuery = (state.locationsSearchQuery || "").trim();

        // Relevance rank slots
        if (searchQuery) {
          slots = slots
            .map(s => ({
              ...s,
              relevanceScore: window.calculateLocationRelevanceScore(s, searchQuery)
            }))
            .filter(s => s.relevanceScore > 0)
            .sort((a, b) => b.relevanceScore - a.relevanceScore);
        }

        if (slots.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">No physical slots match your criteria.</td></tr>`;
          return;
        }

        slots.forEach(s => {
          const tr = document.createElement("tr");
          const isOccupied = s.is_occupied === 1 && s.assigned_design_id;
          const statusBadge = isOccupied ? 
            `<span class="log-status-badge success">Occupied</span>` :
            `<span class="log-status-badge warning">Vacant</span>`;
          
          const hlDesignName = window.highlightKeyword(s.design_name || s.assigned_design_id, searchQuery);
          const hlDesignId = window.highlightKeyword(s.assigned_design_id, searchQuery);
          const hlCategory = window.highlightKeyword(s.design_category || '--', searchQuery);

          const designInfo = isOccupied ?
            `<div style="font-weight: 700;">${hlDesignName}</div><div style="font-size: 0.72rem; font-family: var(--font-mono);">${hlDesignId}</div>` :
            `<span style="color: var(--text-muted); font-style: italic;">Unassigned</span>`;

          const hlSM = window.highlightKeyword(s.shoe_match_name, searchQuery);
          const hlSH = window.highlightKeyword(s.shelf_name, searchQuery);
          const hlDR = window.highlightKeyword(s.drawer_name, searchQuery);
          const hlSL = window.highlightKeyword(s.slot_name, searchQuery);

          const path = `${hlSM} &bull; ${hlSH} &bull; ${hlDR} &bull; <strong>${hlSL}</strong>`;
          const rawPath = `${s.shoe_match_name} > ${s.shelf_name} > ${s.drawer_name} > ${s.slot_name}`;

          tr.innerHTML = `
            <td style="font-size: 0.84rem;">${path}</td>
            <td>${statusBadge}</td>
            <td>${designInfo}</td>
            <td><span style="font-size: 0.8rem; font-weight: 600;">${hlCategory}</span></td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="openAssignLocationModal(${s.slot_id}, '${(s.assigned_design_id || '').replace(/'/g, "\\'")}', '${rawPath.replace(/'/g, "\\'")}')" style="font-size: 0.72rem; padding: 2px 8px;">
                ${isOccupied ? 'Reassign' : 'Assign'}
              </button>
              ${isOccupied ? `<button class="btn btn-secondary btn-sm" onclick="unassignLocationSlot(${s.slot_id})" style="font-size: 0.72rem; padding: 2px 8px; margin-left: 4px;">Vacate</button>` : ''}
            </td>
          `;

          tbody.appendChild(tr);
        });
      }
    } catch (err) {
      console.error("Failed to fetch flat slots table:", err);
    }
  }

  // Location Modal Handlers
  window.openAddLocationModal = function(level = 'shoe_match', smId = null, shelfId = null, drawerId = null) {
    const modal = document.getElementById("add-location-modal");
    const form = document.getElementById("add-location-form");
    if (form) form.reset();

    const typeSelect = document.getElementById("loc-node-type");
    if (typeSelect) {
      typeSelect.value = level;
      handleLocNodeTypeChange(level);
    }

    if (smId) {
      const smSelect = document.getElementById("select-parent-sm");
      if (smSelect) {
        smSelect.value = smId;
        populateShelvesDropdown(smId);
      }
    }
    if (shelfId) {
      const shelfSelect = document.getElementById("select-parent-shelf");
      if (shelfSelect) {
        shelfSelect.value = shelfId;
        populateDrawersDropdown(shelfId);
      }
    }
    if (drawerId) {
      const drawerSelect = document.getElementById("select-parent-drawer");
      if (drawerSelect) drawerSelect.value = drawerId;
    }

    if (modal) modal.style.display = "flex";
  };

  window.closeAddLocationModal = function() {
    const modal = document.getElementById("add-location-modal");
    if (modal) modal.style.display = "none";
  };

  window.handleLocNodeTypeChange = function(type) {
    const grpSm = document.getElementById("group-parent-sm");
    const grpShelf = document.getElementById("group-parent-shelf");
    const grpDrawer = document.getElementById("group-parent-drawer");

    if (grpSm) grpSm.style.display = (type === "shelf" || type === "drawer" || type === "slot") ? "block" : "none";
    if (grpShelf) grpShelf.style.display = (type === "drawer" || type === "slot") ? "block" : "none";
    if (grpDrawer) grpDrawer.style.display = (type === "slot") ? "block" : "none";

    // Populate Parent Dropdowns
    const smSelect = document.getElementById("select-parent-sm");
    if (smSelect && state.locationHierarchy) {
      smSelect.innerHTML = state.locationHierarchy.map(sm => `<option value="${sm.id}">${sm.name}</option>`).join("");
      if (smSelect.value) populateShelvesDropdown(smSelect.value);
    }
  };

  window.populateShelvesDropdown = function(smId) {
    const shelfSelect = document.getElementById("select-parent-shelf");
    if (!shelfSelect) return;
    const sm = (state.locationHierarchy || []).find(x => x.id === parseInt(smId, 10));
    const shelves = sm ? (sm.shelves || []) : [];
    shelfSelect.innerHTML = shelves.map(sh => `<option value="${sh.id}">${sh.name}</option>`).join("");
    if (shelfSelect.value) populateDrawersDropdown(shelfSelect.value);
  };

  window.populateDrawersDropdown = function(shelfId) {
    const drawerSelect = document.getElementById("select-parent-drawer");
    if (!drawerSelect) return;
    let foundDrawers = [];
    (state.locationHierarchy || []).forEach(sm => {
      (sm.shelves || []).forEach(sh => {
        if (sh.id === parseInt(shelfId, 10)) {
          foundDrawers = sh.drawers || [];
        }
      });
    });
    drawerSelect.innerHTML = foundDrawers.map(dr => `<option value="${dr.id}">${dr.name}</option>`).join("");
  };

  window.handleCreateLocationNode = async function(e) {
    e.preventDefault();
    const type = document.getElementById("loc-node-type").value;
    const name = document.getElementById("loc-node-name").value.trim();
    const desc = document.getElementById("loc-node-desc").value.trim();

    try {
      let endpoint = "";
      let payload = { name };

      if (type === "shoe_match") {
        endpoint = "/api/locations/shoe-matches";
        payload.description = desc;
      } else if (type === "shelf") {
        endpoint = "/api/locations/shelves";
        payload.shoe_match_id = document.getElementById("select-parent-sm").value;
      } else if (type === "drawer") {
        endpoint = "/api/locations/drawers";
        payload.shelf_id = document.getElementById("select-parent-shelf").value;
      } else if (type === "slot") {
        endpoint = "/api/locations/slots";
        payload.drawer_id = document.getElementById("select-parent-drawer").value;
      }

      const res = await window.authenticatedFetch(getApiUrl(endpoint), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create location node");
      }

      showToast(`Location node '${name}' created successfully!`, "success");
      closeAddLocationModal();
      fetchLocationHierarchy();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  window.deleteLocationNode = async function(level, id) {
    if (!confirm(`Are you sure you want to delete this ${level.replace('_', ' ')} node and all its children?`)) return;
    
    let endpoint = "";
    if (level === "shoe_match") endpoint = `/api/locations/shoe-matches/${id}`;
    if (level === "shelf") endpoint = `/api/locations/shelves/${id}`;
    if (level === "drawer") endpoint = `/api/locations/drawers/${id}`;
    if (level === "slot") endpoint = `/api/locations/slots/${id}`;

    try {
      const res = await window.authenticatedFetch(getApiUrl(endpoint), { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      showToast(`${level} node deleted`, "info");
      fetchLocationHierarchy();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Slot Assignment Modal Handlers
  window.openAssignLocationModal = async function(slotId, currentDesignId, pathDisplay) {
    const modal = document.getElementById("assign-location-modal");
    const targetInput = document.getElementById("assign-target-slot-id");
    const pathBox = document.getElementById("assign-slot-path-display");
    const designSelect = document.getElementById("assign-design-select");
    const warningBanner = document.getElementById("assign-warning-banner");

    if (targetInput) targetInput.value = slotId;
    if (pathBox) pathBox.innerHTML = pathDisplay;
    if (warningBanner) warningBanner.style.display = currentDesignId ? "block" : "none";

    // Populate catalog designs dropdown
    if (designSelect) {
      designSelect.innerHTML = '<option value="">-- Select Design to Assign --</option>';
      (state.catalog || []).forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.design_id;
        opt.textContent = `${d.design_id} — ${d.name} (${d.category})`;
        if (d.design_id === currentDesignId) opt.selected = true;
        designSelect.appendChild(opt);
      });
    }

    if (modal) modal.style.display = "flex";
  };

  window.closeAssignLocationModal = function() {
    const modal = document.getElementById("assign-location-modal");
    if (modal) modal.style.display = "none";
  };

  window.handleAssignDesignToSlot = async function(e) {
    e.preventDefault();
    const slotId = document.getElementById("assign-target-slot-id").value;
    const designId = document.getElementById("assign-design-select").value;

    if (!slotId || !designId) {
      showToast("Please select a valid design", "error");
      return;
    }

    try {
      const res = await window.authenticatedFetch(getApiUrl(`/api/locations/slots/${slotId}/assign`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ design_id: designId })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to assign design");
      }

      const data = await res.json();
      showToast(`Design ${designId} assigned to slot! Path: ${data.path}`, "success");
      closeAssignLocationModal();
      fetchLocationHierarchy();
      fetchCatalog();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  window.unassignLocationSlot = async function(slotId) {
    if (!confirm("Vacate this slot? The assigned design will be set to unassigned.")) return;
    try {
      const res = await window.authenticatedFetch(getApiUrl(`/api/locations/slots/${slotId}/unassign`), {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to unassign slot");
      showToast("Slot vacated successfully", "info");
      fetchLocationHierarchy();
      fetchCatalog();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // ==========================================================================
  // Bulk Data Management (CSV/Excel Import)
  // ==========================================================================
  state.bulkImportData = null;

  window.handleBulkImportPreview = async function(e) {
    e.preventDefault();
    const spreadsheetInput = document.getElementById("bulk-spreadsheet-input");
    const zipInput = document.getElementById("bulk-zip-input");
    const previewBtn = document.getElementById("btn-bulk-preview");

    if (!spreadsheetInput || !spreadsheetInput.files || spreadsheetInput.files.length === 0) {
      showToast("Please select a valid CSV or Excel spreadsheet file.", "warning");
      return;
    }

    const formData = new FormData();
    formData.append("file", spreadsheetInput.files[0]);

    if (zipInput && zipInput.files && zipInput.files.length > 0) {
      formData.append("images_zip", zipInput.files[0]);
    }

    if (previewBtn) {
      previewBtn.disabled = true;
      previewBtn.innerHTML = '<span>Parsing & Validating...</span>';
    }

    try {
      const res = await window.authenticatedFetch(getApiUrl("/api/admin/bulk-import/preview"), {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to parse spreadsheet");
      }

      const data = await res.json();
      state.bulkImportData = data;
      renderBulkImportPreview(data);
      showToast(`Spreadsheet validated! ${data.summary.ready_count} rows ready for import.`, "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (previewBtn) {
        previewBtn.disabled = false;
        previewBtn.innerHTML = '<span>Parse & Validate Spreadsheet</span>';
      }
    }
  };

  function renderBulkImportPreview(data) {
    const previewWrap = document.getElementById("bulk-preview-wrap");
    const tbody = document.getElementById("bulk-preview-tbody");
    const statTotal = document.getElementById("bulk-stat-total");
    const statReady = document.getElementById("bulk-stat-ready");
    const statDups = document.getElementById("bulk-stat-duplicates");
    const statErrors = document.getElementById("bulk-stat-errors");

    if (previewWrap) previewWrap.style.display = "block";
    if (tbody) tbody.innerHTML = "";

    const s = data.summary || {};
    if (statTotal) statTotal.textContent = s.total_rows || 0;
    if (statReady) statReady.textContent = s.ready_count || 0;
    if (statDups) statDups.textContent = (s.duplicate_file_count || 0) + (s.duplicate_catalog_count || 0);
    if (statErrors) statErrors.textContent = s.error_count || 0;

    const rows = data.rows || [];
    rows.forEach(r => {
      const tr = document.createElement("tr");
      
      let badgeHtml = "";
      if (r.status === "ready") {
        badgeHtml = `<span class="log-status-badge success">Ready</span>`;
      } else if (r.status === "duplicate_file") {
        badgeHtml = `<span class="log-status-badge warning">Duplicate (In File)</span>`;
      } else if (r.status === "duplicate_catalog") {
        badgeHtml = `<span class="log-status-badge warning">Duplicate (In Catalog)</span>`;
      } else {
        const errText = (r.errors || []).join(", ");
        badgeHtml = `<span class="log-status-badge danger" title="${errText}">Error: ${errText}</span>`;
      }

      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-size: 0.78rem;">#${r._row_num}</td>
        <td style="font-family: var(--font-mono); font-weight: 700;">${r.design_id || '--'}</td>
        <td style="font-weight: 600;">${r.name || '--'}</td>
        <td><span style="font-size: 0.8rem;">${r.category || 'Sneaker'}</span></td>
        <td><span style="font-size: 0.78rem; font-family: var(--font-mono);">${r.images_found_count || 0} photo(s)</span></td>
        <td>${badgeHtml}</td>
      `;

      tbody.appendChild(tr);
    });
  }

  window.handleExecuteBulkImport = async function() {
    if (!state.bulkImportData || !state.bulkImportData.rows) {
      showToast("No validated dataset ready for import", "warning");
      return;
    }

    const strategySelect = document.getElementById("bulk-duplicate-strategy");
    const strategy = strategySelect ? strategySelect.value : "skip";

    const executeBtn = document.getElementById("btn-execute-bulk");
    const progressWrap = document.getElementById("bulk-progress-wrap");
    const progressText = document.getElementById("bulk-progress-text");
    const progressPct = document.getElementById("bulk-progress-pct");
    const progressFill = document.getElementById("bulk-progress-fill");
    const resultsWrap = document.getElementById("bulk-results-wrap");
    const resultsText = document.getElementById("bulk-results-summary-text");
    const exportBtn = document.getElementById("btn-export-failed-csv");

    if (!confirm(`Execute bulk import of ${state.bulkImportData.rows.length} rows? Duplicate handling: '${strategy.toUpperCase()}'.`)) {
      return;
    }

    if (executeBtn) executeBtn.disabled = true;
    if (progressWrap) progressWrap.style.display = "block";
    if (progressFill) progressFill.style.width = "10%";
    if (progressText) progressText.textContent = "Processing rows through AI embedding pipeline...";
    if (progressPct) progressPct.textContent = "10%";

    try {
      const res = await window.authenticatedFetch(getApiUrl("/api/admin/bulk-import/execute"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rows: state.bulkImportData.rows,
          duplicate_handling: strategy
        })
      });

      if (progressFill) progressFill.style.width = "100%";
      if (progressPct) progressPct.textContent = "100%";

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Bulk import execution failed");
      }

      const result = await res.json();
      state.lastBulkResult = result;

      if (resultsWrap) resultsWrap.style.display = "block";
      if (resultsText) {
        resultsText.innerHTML = `
          <strong>Import Complete!</strong><br>
          • Total Processed: <strong>${result.total_processed}</strong><br>
          • Successfully Ingested: <strong style="color: var(--status-success-text);">${result.succeeded}</strong><br>
          • Skipped (Duplicates): <strong>${result.skipped}</strong><br>
          • Failed Rows: <strong style="color: var(--status-danger-text);">${result.failed}</strong>
        `;
      }

      if (exportBtn) {
        exportBtn.style.display = result.failed > 0 ? "block" : "none";
      }

      showToast(`Bulk Import Finished! Ingested: ${result.succeeded}, Failed: ${result.failed}, Skipped: ${result.skipped}`, "success");
      fetchCatalog();
      fetchStats();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (executeBtn) executeBtn.disabled = false;
    }
  };

  window.handleExportFailedCSV = async function() {
    if (!state.lastBulkResult || !state.lastBulkResult.details) {
      showToast("No failed rows recorded in current session", "warning");
      return;
    }

    try {
      const res = await window.authenticatedFetch(getApiUrl("/api/admin/bulk-import/export-failed"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ details: state.lastBulkResult.details })
      });

      if (!res.ok) throw new Error("Failed to generate CSV export");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "failed_import_rows.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast("Downloaded failed_import_rows.csv", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Start Application
  init();
});
