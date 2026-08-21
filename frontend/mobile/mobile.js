/**
 * ShoeMatch AI — Material Design 3 Native Mobile Application Logic
 */

(function () {
  'use strict';

  // State Management
  const state = {
    user: null,
    selectedQueryFile: null,
    catalog: [],
    mobileTarget: localStorage.getItem("shoematch_mobile_target") || "wifi"
  };

  // ==========================================
  // API URL & Token Persistence Helpers
  // ==========================================
  window.getApiBaseUrl = function () {
    try {
      const saved = localStorage.getItem("shoematch_api_base_url");
      if (saved && saved.trim()) {
        let url = saved.trim();
        return url.endsWith("/") ? url.slice(0, -1) : url;
      }
    } catch (e) {}

    if (window.Capacitor && window.Capacitor.isNativePlatform()) {
      try {
        const mode = localStorage.getItem("shoematch_mobile_target");
        if (mode === "emulator") {
          return "http://10.0.2.2:8000";
        }
      } catch (e) {}
      return "http://192.168.1.15:8000";
    }
    return "";
  };

  window.getApiUrl = function (path) {
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:") || path.startsWith("blob:")) {
      return path;
    }
    const base = window.getApiBaseUrl();
    const cleanPath = path.startsWith("/") ? path : "/" + path;
    return base ? base + cleanPath : cleanPath;
  };

  window._cachedAuthToken = null;

  window.getAuthToken = function () {
    if (window._cachedAuthToken !== null) return window._cachedAuthToken;
    try {
      const local = localStorage.getItem("shoematch_auth_token") || "";
      window._cachedAuthToken = local;
      return local;
    } catch (e) {
      return "";
    }
  };

  window.setAuthToken = function (token) {
    window._cachedAuthToken = token || "";
    try {
      if (token) localStorage.setItem("shoematch_auth_token", token);
      else localStorage.removeItem("shoematch_auth_token");
    } catch (e) {}

    try {
      if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Preferences) {
        const prefs = window.Capacitor.Plugins.Preferences;
        if (token) prefs.set({ key: "shoematch_auth_token", value: token });
        else prefs.remove({ key: "shoematch_auth_token" });
      }
    } catch (e) {}
  };

  window.authenticatedFetch = async function (url, options = {}) {
    const token = window.getAuthToken();
    options.headers = options.headers || {};
    if (token && !options.headers["Authorization"]) {
      options.headers["Authorization"] = `Bearer ${token}`;
    }
    return fetch(url, options);
  };

  window.extractErrorMessage = function (err, fallback = "An unexpected error occurred") {
    if (!err) return fallback;
    if (typeof err === "string") return err;

    if (err.detail) {
      if (typeof err.detail === "string") return err.detail;
      if (Array.isArray(err.detail)) {
        return err.detail.map(item => item.msg || (typeof item === "string" ? item : JSON.stringify(item))).join("; ");
      }
      if (typeof err.detail === "object") return JSON.stringify(err.detail);
    }

    if (err.message && typeof err.message === "string") return err.message;
    if (err.error && typeof err.error === "string") return err.error;

    try {
      return JSON.stringify(err);
    } catch (e) {
      return String(err);
    }
  };

  // ==========================================
  // UI Tab Navigation & Theme Controller
  // ==========================================
  function initNavigation() {
    const navTabs = document.querySelectorAll(".nav-tab");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const targetTab = tab.dataset.tab;
        navTabs.forEach(t => t.classList.toggle("active", t.dataset.tab === targetTab));
        tabPanes.forEach(p => p.classList.toggle("active", p.id === targetTab));

        if (targetTab === "tab-catalog") fetchCatalog();
        if (targetTab === "tab-locations") searchLocations("");
        if (targetTab === "tab-admin") fetchAuditLogs();
      });
    });
  }

  function initTheme() {
    const themeBtn = document.getElementById("btn-theme-toggle");
    const savedTheme = localStorage.getItem("shoematch_theme") || "light";
    document.documentElement.dataset.theme = savedTheme;

    themeBtn.addEventListener("click", () => {
      const current = document.documentElement.dataset.theme;
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("shoematch_theme", next);
    });
  }

  // ==========================================
  // Auth & Session Management
  // ==========================================
  async function checkAuthStatus() {
    const token = window.getAuthToken();
    if (!token) {
      showModal("auth-modal");
      return;
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/users/me"));
      if (res.status === 401) {
        window.setAuthToken("");
        showModal("auth-modal");
        return;
      }
      if (res.status === 403) {
        const data = await res.json();
        if (data.detail && data.detail.includes("Password change required")) {
          showModal("password-reset-modal");
          return;
        }
      }

      if (res.ok) {
        const user = await res.json();
        state.user = user;
        hideModal("auth-modal");
        hideModal("password-reset-modal");
        updateUserRoleBadge(user);
      }
    } catch (err) {
      console.warn("Auth status check warning:", err);
    }
  }

  function updateUserRoleBadge(user) {
    const roleBadge = document.getElementById("role-badge");
    const adminTab = document.getElementById("nav-tab-admin");

    if (roleBadge) roleBadge.textContent = user.role.toUpperCase();
    if (adminTab) {
      if (user.role === "admin") adminTab.classList.remove("hidden");
      else adminTab.classList.add("hidden");
    }
  }

  function showModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("hidden");
  }
  function hideModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
  }

  function initAuthEvents() {
    const loginForm = document.getElementById("login-form");
    const loginErr = document.getElementById("login-error-text");

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      loginErr.textContent = "";
      const u = document.getElementById("login-username").value.trim();
      const p = document.getElementById("login-password").value.trim();

      if (!u || !p) {
        loginErr.textContent = "Please enter both username and password";
        return;
      }

      try {
        const res = await fetch(window.getApiUrl("/api/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: u, password: p })
        });

        if (!res.ok) {
          let errData;
          try {
            errData = await res.json();
          } catch (e) {
            errData = { detail: `Server error (Status ${res.status})` };
          }
          loginErr.textContent = window.extractErrorMessage(errData, "Invalid username or password");
          return;
        }

        const data = await res.json();
        const token = data.token || data.access_token || "";
        if (!token) {
          loginErr.textContent = "Authentication succeeded but no token was returned";
          return;
        }

        window.setAuthToken(token);
        await checkAuthStatus();
      } catch (err) {
        loginErr.textContent = window.extractErrorMessage(err, "Network error connecting to API server");
      }
    });

    const logoutBtn = document.getElementById("btn-logout");
    logoutBtn.addEventListener("click", () => {
      window.setAuthToken("");
      state.user = null;
      showModal("auth-modal");
    });
  }

  // ==========================================
  // Camera & Image Capture Flow
  // ==========================================
  function initCameraEvents() {
    const cameraBtn = document.getElementById("btn-studio-camera");
    const fabCamera = document.getElementById("fab-camera-capture");
    const galleryBtn = document.getElementById("btn-studio-gallery");
    const filePicker = document.getElementById("file-gallery-picker");

    async function handleCameraCapture() {
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
            return;
          }
        } catch (err) {
          console.warn("Capacitor camera error/cancel:", err);
        }
      }
      filePicker.click();
    }

    cameraBtn.addEventListener("click", handleCameraCapture);
    fabCamera.addEventListener("click", handleCameraCapture);

    galleryBtn.addEventListener("click", () => filePicker.click());
    filePicker.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        setQueryFile(e.target.files[0]);
      }
    });

    const executeBtn = document.getElementById("btn-execute-match");
    executeBtn.addEventListener("click", runVisualMatch);
  }

  function setQueryFile(file) {
    state.selectedQueryFile = file;
    const previewContainer = document.getElementById("query-preview-container");
    const previewImg = document.getElementById("query-preview-img");

    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewContainer.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
  }

  // ==========================================
  // Staged AI Scanning & Match Execution
  // ==========================================
  async function runVisualMatch() {
    if (!state.selectedQueryFile) return;

    const overlay = document.getElementById("scanner-overlay");
    const statusText = document.getElementById("scanner-status-text");
    const stepExif = document.getElementById("step-exif");
    const stepU2Net = document.getElementById("step-u2net");
    const stepDINO = document.getElementById("step-dinov2");
    const stepFAISS = document.getElementById("step-faiss");

    overlay.classList.remove("hidden");
    [stepExif, stepU2Net, stepDINO, stepFAISS].forEach(s => s.className = "scan-step");

    // Staged Feedback Animation Sequence
    statusText.textContent = "Checking Image Orientation...";
    stepExif.classList.add("active");

    setTimeout(() => {
      stepExif.classList.replace("active", "done");
      stepU2Net.classList.add("active");
      statusText.textContent = "Segmenting Shoe Cutout...";
    }, 400);

    setTimeout(() => {
      stepU2Net.classList.replace("active", "done");
      stepDINO.classList.add("active");
      statusText.textContent = "Extracting DINOv2 Feature Vector...";
    }, 1000);

    setTimeout(() => {
      stepDINO.classList.replace("active", "done");
      stepFAISS.classList.add("active");
      statusText.textContent = "FAISS Similarity Search...";
    }, 1800);

    const formData = new FormData();
    formData.append("file", state.selectedQueryFile);

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/match"), {
        method: "POST",
        body: formData
      });

      overlay.classList.add("hidden");

      if (!res.ok) {
        let errData;
        try { errData = await res.json(); } catch(e) { errData = { detail: `Match request failed (Status ${res.status})` }; }
        alert(window.extractErrorMessage(errData, "Error performing visual match."));
        return;
      }

      const matchData = await res.json();
      renderMatchResults(matchData);
    } catch (err) {
      overlay.classList.add("hidden");
      alert("Network error connecting to matching server.");
    }
  }

  function renderMatchResults(data) {
    const alertContainer = document.getElementById("slipper-alert-container");
    const resultsContainer = document.getElementById("match-results-container");

    alertContainer.classList.add("hidden");
    resultsContainer.innerHTML = "";

    if (data.reason === "slipper_rejected" || data.reason === "no_shoe") {
      alertContainer.classList.remove("hidden");
      return;
    }

    const matches = data.matches || [];
    if (matches.length === 0) {
      resultsContainer.innerHTML = `<div class="md-card">No catalog matches found.</div>`;
      return;
    }

    matches.forEach((m, idx) => {
      const rank = idx + 1;
      const confidence = (m.confidence_pct || 0).toFixed(1);
      const design = m.design || {};
      const imgPath = window.getApiUrl(m.image_path || (design.thumbnail_path || ''));

      const card = document.createElement("div");
      card.className = `md-card match-card rank-${rank}`;

      card.innerHTML = `
        <div class="match-badge">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span>#${rank} MATCH • ${confidence}% CONFIDENCE</span>
        </div>
        <div class="card-title">${design.name || m.design_id}</div>
        <div style="font-size: 0.8rem; color: var(--md-sys-color-outline); margin-bottom: 12px;">SKU: ${m.design_id} • ${design.category || 'Footwear'}</div>
        
        <img src="${imgPath}" style="width: 100%; max-height: 180px; object-fit: contain; border-radius: 12px; margin-bottom: 12px; background-color: var(--md-sys-color-background);" />
        
        <div style="font-size: 0.82rem; color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">
          Upper: <strong>${design.upper_material || 'N/A'}</strong> • Sole: <strong>${design.sole_material || 'N/A'}</strong>
        </div>

        <div class="location-chip">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${design.zone_id || 'Zone A'} → ${design.shelf_id || 'Shelf 01'} → ${design.drawer_id || 'D1'} → ${design.slot_id || 'S1'}</span>
        </div>
      `;
      resultsContainer.appendChild(card);
    });
  }

  // ==========================================
  // Catalog & Search Logic
  // ==========================================
  async function fetchCatalog() {
    const grid = document.getElementById("catalog-grid");
    grid.innerHTML = `<div class="md-card">Loading catalog designs...</div>`;

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/designs"));
      if (!res.ok) return;

      const data = await res.json();
      state.catalog = data.designs || data || [];
      renderCatalog(state.catalog);
    } catch (err) {
      grid.innerHTML = `<div class="md-card">Error loading catalog.</div>`;
    }
  }

  function renderCatalog(items) {
    const grid = document.getElementById("catalog-grid");
    grid.innerHTML = "";

    if (items.length === 0) {
      grid.innerHTML = `<div class="md-card">No designs found.</div>`;
      return;
    }

    items.forEach(item => {
      const imgPath = window.getApiUrl(item.thumbnail_path || (item.reference_images && item.reference_images[0] ? item.reference_images[0].image_path : ''));
      const card = document.createElement("div");
      card.className = "md-card";

      card.innerHTML = `
        <div style="font-size: 0.75rem; font-weight: 700; color: var(--md-sys-color-secondary);">${item.design_id}</div>
        <div class="card-title">${item.name}</div>
        <img src="${imgPath}" style="width: 100%; height: 140px; object-fit: contain; border-radius: 12px; margin: 8px 0; background-color: var(--md-sys-color-background);" />
        <div style="font-size: 0.8rem; color: var(--md-sys-color-on-surface-variant);">
          ${item.category} • ${item.upper_material} / ${item.sole_material}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  function initCatalogSearch() {
    const input = document.getElementById("catalog-search-input");
    input.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        renderCatalog(state.catalog);
        return;
      }
      const filtered = state.catalog.filter(i => 
        (i.name && i.name.toLowerCase().includes(q)) ||
        (i.design_id && i.design_id.toLowerCase().includes(q)) ||
        (i.category && i.category.toLowerCase().includes(q))
      );
      renderCatalog(filtered);
    });
  }

  // ==========================================
  // Location Hierarchy Search
  // ==========================================
  async function searchLocations(query) {
    const container = document.getElementById("location-results-container");
    try {
      const res = await window.authenticatedFetch(window.getApiUrl(`/api/locations/search?q=${encodeURIComponent(query)}`));
      if (!res.ok) return;

      const data = await res.json();
      renderLocationResults(data.results || [], query);
    } catch (err) {}
  }

  function renderLocationResults(items, query) {
    const container = document.getElementById("location-results-container");
    container.innerHTML = "";

    if (items.length === 0) {
      container.innerHTML = `<div class="md-card">No storage locations match your query.</div>`;
      return;
    }

    items.forEach(item => {
      const card = document.createElement("div");
      card.className = "md-card";

      let title = item.name || item.design_id;
      let locText = `${item.zone_id} → ${item.shelf_id} → ${item.drawer_id} → ${item.slot_id}`;

      if (query) {
        const regex = new RegExp(`(${query})`, "gi");
        title = title.replace(regex, `<mark class="highlight">$1</mark>`);
        locText = locText.replace(regex, `<mark class="highlight">$1</mark>`);
      }

      card.innerHTML = `
        <div style="font-size: 0.75rem; font-weight: 700; color: var(--md-sys-color-secondary);">${item.design_id}</div>
        <div class="card-title">${title}</div>
        <div class="location-chip" style="margin-top: 6px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${locText}</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function initLocationEvents() {
    const input = document.getElementById("location-search-input");
    input.addEventListener("input", (e) => {
      searchLocations(e.target.value.trim());
    });
  }

  // ==========================================
  // Admin Audit Logs
  // ==========================================
  async function fetchAuditLogs() {
    const container = document.getElementById("admin-audit-logs");
    container.innerHTML = `<div>Loading audit logs...</div>`;

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/admin/audit-logs"));
      if (!res.ok) {
        container.innerHTML = `<div style="color: var(--md-sys-color-error);">Access Denied (Admin role required)</div>`;
        return;
      }

      const data = await res.json();
      const logs = data.logs || [];
      container.innerHTML = "";

      logs.forEach(log => {
        const item = document.createElement("div");
        item.style.padding = "10px 0";
        item.style.borderBottom = "1px solid var(--md-sys-color-surface-variant)";
        item.style.fontSize = "0.82rem";

        item.innerHTML = `
          <div style="font-weight: 700; color: var(--md-sys-color-primary);">${log.action}</div>
          <div style="color: var(--md-sys-color-on-surface-variant);">${log.details || ''}</div>
          <div style="font-size: 0.72rem; color: var(--md-sys-color-outline); margin-top: 2px;">${log.timestamp} • User #${log.user_id}</div>
        `;
        container.appendChild(item);
      });
    } catch (err) {
      container.innerHTML = `<div>Error fetching logs.</div>`;
    }
  }

  // ==========================================
  // Boot & Initialization
  // ==========================================
  document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initTheme();
    initAuthEvents();
    initCameraEvents();
    initCatalogSearch();
    initLocationEvents();

    const hostIndicator = document.getElementById("target-host-indicator");
    if (hostIndicator) {
      hostIndicator.textContent = window.getApiBaseUrl() || "Relative Host";
      hostIndicator.style.cursor = "pointer";
      hostIndicator.title = "Tap to change Server IP";
      hostIndicator.addEventListener("click", () => {
        const current = window.getApiBaseUrl() || "http://192.168.1.15:8000";
        const custom = prompt("Enter Server Base URL (e.g. http://192.168.1.15:8000):", current);
        if (custom !== null) {
          if (custom.trim()) {
            localStorage.setItem("shoematch_api_base_url", custom.trim());
          } else {
            localStorage.removeItem("shoematch_api_base_url");
          }
          hostIndicator.textContent = window.getApiBaseUrl() || "Relative Host";
          checkAuthStatus();
        }
      });
    }

    checkAuthStatus();
  });

})();
