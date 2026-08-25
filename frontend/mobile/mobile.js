/**
 * ShoeMatch AI — Material Design 3 Native Mobile Application Logic
 */

(function () {
  'use strict';

  // ==========================================================================
  // ⚠️ DEV BYPASS — SET TO false BEFORE SHARING BUILD OR DEPLOYING TO PRODUCTION
  // ==========================================================================
  const DEV_SKIP_LOGIN = true;

  // State Management
  const state = {
    user: null,
    selectedQueryFile: null,
    selectedCatalogAddFile: null,
    catalog: [],
    existingFarmaShelves: [],
    mobileTarget: localStorage.getItem("shoematch_mobile_target") || "wifi"
  };

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

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
      // Otherwise fall through to SHOEMATCH_API_BASE (config.js)
    }

    // Deployed configuration (frontend/config.js). Empty = same-origin.
    if (window.SHOEMATCH_API_BASE) {
      const cfg = String(window.SHOEMATCH_API_BASE).trim();
      if (cfg) return cfg.endsWith("/") ? cfg.slice(0, -1) : cfg;
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
    const themeLabel = document.getElementById("theme-toggle-label");
    const savedTheme = localStorage.getItem("shoematch_theme") || "light";
    document.documentElement.dataset.theme = savedTheme;
    if (themeLabel) themeLabel.textContent = (savedTheme === "dark") ? "Light Mode" : "Dark Mode";

    if (themeBtn) {
      themeBtn.addEventListener("click", () => {
        const current = document.documentElement.dataset.theme;
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        localStorage.setItem("shoematch_theme", next);
        if (themeLabel) themeLabel.textContent = (next === "dark") ? "Light Mode" : "Dark Mode";
      });
    }

    const switchRoleBtn = document.getElementById("btn-switch-account-role");
    if (switchRoleBtn) {
      switchRoleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        toggleAccountRole();
      });
    }
  }

  function getActiveRole() {
    return localStorage.getItem("shoematch_active_role") || "admin";
  }

  function applyActiveRole(role) {
    const cleanRole = (role || "").toLowerCase() === "employee" ? "employee" : "admin";
    state.currentRole = cleanRole;
    localStorage.setItem("shoematch_active_role", cleanRole);

    const headerBadge = document.getElementById("role-badge");
    if (headerBadge) {
      headerBadge.textContent = cleanRole === "admin" ? "Admin" : "Employee";
    }

    const adminNavTab = document.getElementById("nav-tab-admin");
    if (adminNavTab) {
      adminNavTab.classList.remove("hidden");
    }

    const userDisplayName = document.getElementById("admin-user-display-name");
    const adminRoleBadge = document.getElementById("admin-role-badge");
    const switchRoleBtnText = document.getElementById("switch-role-btn-text");

    if (userDisplayName) {
      userDisplayName.textContent = cleanRole === "admin" ? "Admin Account" : "Employee Account";
    }

    if (adminRoleBadge) {
      adminRoleBadge.textContent = cleanRole === "admin" ? "Admin" : "Employee";
    }

    if (switchRoleBtnText) {
      switchRoleBtnText.textContent = cleanRole === "admin" ? "Switch to Employee Account" : "Switch to Admin Account";
    }
  }

  function toggleAccountRole() {
    const current = getActiveRole();
    const nextRole = current === "admin" ? "employee" : "admin";
    applyActiveRole(nextRole);

    addActivityLog({
      action: "Account Role Switched",
      details: `Active user role switched to ${nextRole === "admin" ? "Admin" : "Employee"}.`,
      type: "role_switch"
    });
  }

  // ==========================================
  // Auth & Session Management
  // ==========================================
  async function checkAuthStatus() {
    // ⚠️ Temporary Dev-Only Testing Bypass
    if (DEV_SKIP_LOGIN) {
      hideModal("auth-modal");
      hideModal("password-reset-modal");

      // Auto-authenticate in background with default admin credentials if no token exists
      if (!window.getAuthToken()) {
        try {
          const autoRes = await fetch(window.getApiUrl("/api/auth/login"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: "admin", password: "admin123" })
          });
          if (autoRes.ok) {
            const autoData = await autoRes.json();
            const t = autoData.token || autoData.access_token;
            if (t) window.setAuthToken(t);
          }
        } catch (e) {
          console.warn("Dev bypass background auto-login attempt failed:", e);
        }
      }

      state.user = {
        user_id: 1,
        username: "dev_tester",
        role: "admin",
        full_name: "Development Test User"
      };
      updateUserRoleBadge(state.user);
      return;
    }

    // Production Auth Flow
    const token = window.getAuthToken();
    if (!token) {
      showModal("auth-modal");
      return;
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/auth/me"));
      if (res.status === 401) {
        window.setAuthToken("");
        showModal("auth-modal");
        return;
      }

      if (res.ok) {
        const data = await res.json();
        const userObj = data.user || data;
        state.user = userObj;
        hideModal("auth-modal");
        hideModal("password-reset-modal");
        updateUserRoleBadge(userObj);
      }
    } catch (err) {
      console.warn("Auth status check warning:", err);
    }
  }

  function updateUserRoleBadge(user) {
    applyActiveRole(getActiveRole());
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
      let u = document.getElementById("login-username").value.trim();
      let p = document.getElementById("login-password").value.trim();

      if (u.toLowerCase() === "admin" && !p) p = "admin123";
      if (u.toLowerCase() === "employee" && !p) p = "emp123";

      if (!u) {
        loginErr.textContent = "Please enter a username (e.g. admin or employee)";
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

  function switchTab(tabId) {
    const navTabs = document.querySelectorAll(".nav-tab");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navTabs.forEach(t => t.classList.toggle("active", t.dataset.tab === tabId));
    tabPanes.forEach(p => p.classList.toggle("active", p.id === tabId));

    if (tabId === "tab-catalog") fetchCatalog();
    if (tabId === "tab-admin") fetchAuditLogs();

    const mainContent = document.querySelector(".main-content");
    if (mainContent) mainContent.scrollTop = 0;
  }

  function setQueryFile(file, autoRun = true) {
    state.selectedQueryFile = file;
    const previewContainer = document.getElementById("query-preview-container");
    const previewImg = document.getElementById("query-preview-img");

    // Instantly switch & redirect to Studio tab
    switchTab("tab-studio");

    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewImg) previewImg.src = e.target.result;
      if (previewContainer) previewContainer.classList.remove("hidden");
      
      // Automatically & instantly run AI search upon photo capture
      if (autoRun) {
        runVisualMatch();
      }
    };
    reader.readAsDataURL(file);
  }

  async function fetchFarmaShelves() {
    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/designs/farma-shelves"));
      if (res.ok) {
        const data = await res.json();
        state.existingFarmaShelves = data.farma_shelves || [];
      }
    } catch (err) {
      console.warn("Could not fetch farma shelves:", err);
    }
  }

  function setupCombobox({ inputId, dropdownId, getSuggestions, newItemPrefix, onDeleteItem }) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;

    function render(query = "") {
      const q = (query || "").trim().toLowerCase();
      const all = getSuggestions() || [];

      let startsWithMatches = [];
      let includesMatches = [];

      all.forEach(item => {
        if (!item || typeof item !== 'string') return;
        const s = item.toLowerCase();
        if (!q) {
          startsWithMatches.push(item);
        } else if (s.startsWith(q)) {
          startsWithMatches.push(item);
        } else if (s.includes(q)) {
          includesMatches.push(item);
        }
      });

      const matches = [...startsWithMatches, ...includesMatches];
      const exactMatch = all.some(s => s && typeof s === 'string' && s.toLowerCase() === q);

      let html = "";

      matches.forEach(item => {
        html += `
          <div class="farma-shelf-item" data-value="${escapeHtml(item)}" style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6"/><path d="M12 9v6M9 12h6"/></svg>
              <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(item)}</span>
            </div>
            ${onDeleteItem ? `
            <button type="button" class="combobox-delete-item-btn" data-delete-val="${escapeHtml(item)}" title="Delete Option" style="background: none; border: none; padding: 4px 6px; cursor: pointer; color: var(--md-sys-color-error); border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
            ` : ''}
          </div>
        `;
      });

      if (q && !exactMatch) {
        html += `
          <div class="farma-shelf-item farma-shelf-item-new" data-value="${escapeHtml(query.trim())}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>${newItemPrefix || "Add new"}: "${escapeHtml(query.trim())}"</span>
          </div>
        `;
      }

      if (!html) {
        dropdown.classList.add("hidden");
        return;
      }

      dropdown.innerHTML = html;
      dropdown.classList.remove("hidden");

      dropdown.querySelectorAll(".farma-shelf-item").forEach(el => {
        el.addEventListener("mousedown", (e) => {
          if (e.target.closest(".combobox-delete-item-btn")) {
            e.preventDefault();
            e.stopPropagation();
            const btn = e.target.closest(".combobox-delete-item-btn");
            const valToDelete = btn.getAttribute("data-delete-val");
            if (valToDelete && onDeleteItem) {
              onDeleteItem(valToDelete);
              render(input.value);
            }
            return;
          }

          e.preventDefault();
          const val = el.getAttribute("data-value");
          input.value = val;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          dropdown.classList.add("hidden");
        });
      });
    }

    input.addEventListener("focus", () => {
      fetchFarmaShelves();
      render(input.value);
    });

    input.addEventListener("input", () => {
      render(input.value);
    });

    input.addEventListener("blur", () => {
      setTimeout(() => dropdown.classList.add("hidden"), 200);
    });
  }

  function initCatalogAddComboboxes() {
    // 1. Design Name Combobox
    setupCombobox({
      inputId: "catalog-add-name-input",
      dropdownId: "design-name-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedNames || [];
        const fromCatalog = (state.catalog || []).map(d => d.name).filter(Boolean);
        return Array.from(new Set(fromCatalog)).filter(n => !deleted.includes(n));
      },
      newItemPrefix: "Add new name",
      onDeleteItem: (val) => {
        state.customDeletedNames = state.customDeletedNames || [];
        state.customDeletedNames.push(val);
        addActivityLog({
          action: "Design Name Option Deleted",
          details: `Removed "${val}" from Design Name selection options.`,
          type: "catalog_edit"
        });
      }
    });

    // 2. Category Combobox
    setupCombobox({
      inputId: "catalog-add-category-input",
      dropdownId: "category-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedCategories || [];
        const defaults = ["Sneaker", "Formal Shoe", "Casual Shoe", "Slipper", "Sandal", "Boot", "Loafer", "Mule", "Sports Shoe"];
        const fromCatalog = (state.catalog || []).map(d => d.category).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(c => !deleted.includes(c));
      },
      newItemPrefix: "Add new category",
      onDeleteItem: (val) => {
        state.customDeletedCategories = state.customDeletedCategories || [];
        state.customDeletedCategories.push(val);
        addActivityLog({
          action: "Category Option Deleted",
          details: `Removed "${val}" from Category selection options.`,
          type: "catalog_edit"
        });
      }
    });

    // 3. Farma Shelf Combobox
    setupCombobox({
      inputId: "catalog-add-farma-shelf-input",
      dropdownId: "farma-shelf-dropdown",
      getSuggestions: () => state.existingFarmaShelves || [],
      newItemPrefix: "Add new shelf",
      onDeleteItem: (val) => {
        state.existingFarmaShelves = (state.existingFarmaShelves || []).filter(s => s !== val);
        addActivityLog({
          action: "Farma Shelf Option Deleted",
          details: `Removed "${val}" from Farma Shelf selection options.`,
          type: "catalog_edit"
        });
        updateAdminDashboard();
      }
    });

    // 4. Drawer Combobox
    setupCombobox({
      inputId: "catalog-add-drawer-input",
      dropdownId: "add-drawer-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedDrawers || [];
        const defaults = ["Drawer 01", "Drawer A-04", "Top Drawer", "Drawer B-02"];
        const fromCatalog = (state.catalog || []).map(d => d.drawer || d.season).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(d => !deleted.includes(d));
      },
      newItemPrefix: "Add new drawer",
      onDeleteItem: (val) => {
        state.customDeletedDrawers = state.customDeletedDrawers || [];
        state.customDeletedDrawers.push(val);
        addActivityLog({
          action: "Drawer Option Deleted",
          details: `Removed "${val}" from Drawer selection options.`,
          type: "catalog_edit"
        });
      }
    });

    // 5. Warehouse Location Combobox
    setupCombobox({
      inputId: "catalog-add-location-input",
      dropdownId: "add-location-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedLocations || [];
        const defaults = ["Warehouse A - Rack 01 - Shelf A-01", "Warehouse A - Rack 03 - Shelf B-02", "Warehouse B - Rack 05 - Shelf C-01"];
        const fromCatalog = (state.catalog || []).map(d => d.shelf_location).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(l => !deleted.includes(l));
      },
      newItemPrefix: "Add new location",
      onDeleteItem: (val) => {
        state.customDeletedLocations = state.customDeletedLocations || [];
        state.customDeletedLocations.push(val);
        addActivityLog({
          action: "Warehouse Location Option Deleted",
          details: `Removed "${val}" from Warehouse Location selection options.`,
          type: "catalog_edit"
        });
      }
    });

    // 6. Materials Combobox
    setupCombobox({
      inputId: "catalog-add-materials-input",
      dropdownId: "add-materials-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedMaterials || [];
        const defaults = ["Full Grain Leather / Rubber Sole", "Knit Mesh / Foam Sole", "Suede Leather / Rubber Sole", "Canvas Upper / Vulcanized Sole"];
        const fromCatalog = (state.catalog || []).map(d => d.materials).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(m => !deleted.includes(m));
      },
      newItemPrefix: "Add new material",
      onDeleteItem: (val) => {
        state.customDeletedMaterials = state.customDeletedMaterials || [];
        state.customDeletedMaterials.push(val);
        addActivityLog({
          action: "Materials Option Deleted",
          details: `Removed "${val}" from Materials selection options.`,
          type: "catalog_edit"
        });
      }
    });

    // 7. Season Combobox
    setupCombobox({
      inputId: "catalog-add-season-input",
      dropdownId: "add-season-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedSeasons || [];
        const defaults = ["Collection 2026", "Summer 2026", "Winter 2025", "Autumn Archive"];
        const fromCatalog = (state.catalog || []).map(d => d.season).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(s => !deleted.includes(s));
      },
      newItemPrefix: "Add new season",
      onDeleteItem: (val) => {
        state.customDeletedSeasons = state.customDeletedSeasons || [];
        state.customDeletedSeasons.push(val);
        addActivityLog({
          action: "Season Option Deleted",
          details: `Removed "${val}" from Season selection options.`,
          type: "catalog_edit"
        });
      }
    });
  }

  window.computeDynamicSkuFromDetails = function(details) {
    const fields = [
      details.category,
      details.name,
      details.farma_shelf,
      details.drawer,
      details.shelf_location,
      details.materials
    ];

    const parts = [];
    fields.forEach(val => {
      if (val && typeof val === 'string') {
        const clean = val.trim().replace(/[^a-zA-Z0-9]/g, '');
        if (clean.length > 0) {
          parts.push(clean.substring(0, 2).toUpperCase());
        }
      }
    });

    return parts.length > 0 ? parts.join("-") : "SKU";
  };

  window.updateAddModalLiveSku = function() {
    const cat = document.getElementById("catalog-add-category-input")?.value || "";
    const name = document.getElementById("catalog-add-name-input")?.value || "";
    const shelf = document.getElementById("catalog-add-farma-shelf-input")?.value || "";
    const drawer = document.getElementById("catalog-add-drawer-input")?.value || "";
    const loc = document.getElementById("catalog-add-location-input")?.value || "";
    const mat = document.getElementById("catalog-add-materials-input")?.value || "";

    const sku = window.computeDynamicSkuFromDetails({
      category: cat,
      name: name,
      farma_shelf: shelf,
      drawer: drawer,
      shelf_location: loc,
      materials: mat
    });

    const badge = document.getElementById("catalog-add-sku-badge");
    if (badge) badge.textContent = sku;
  };

  window.updateEditModalLiveSku = function() {
    const cat = document.getElementById("catalog-edit-category-input")?.value || "";
    const name = document.getElementById("catalog-edit-name-input")?.value || "";
    const shelf = document.getElementById("catalog-edit-farma-shelf-input")?.value || "";
    const drawer = document.getElementById("catalog-edit-drawer-input")?.value || "";
    const loc = document.getElementById("catalog-edit-location-input")?.value || "";
    const mat = document.getElementById("catalog-edit-materials-input")?.value || "";

    const sku = window.computeDynamicSkuFromDetails({
      category: cat,
      name: name,
      farma_shelf: shelf,
      drawer: drawer,
      shelf_location: loc,
      materials: mat
    });

    const skuInput = document.getElementById("catalog-edit-sku-input");
    if (skuInput) skuInput.value = sku;
  };

  function initCatalogAddEvents() {
    const cameraBtn = document.getElementById("btn-catalog-add-camera");
    const galleryBtn = document.getElementById("btn-catalog-add-gallery");
    const filePicker = document.getElementById("file-catalog-add-picker");
    const submitBtn = document.getElementById("btn-catalog-add-submit");

    initCatalogAddComboboxes();

    ["catalog-add-category-input", "catalog-add-name-input", "catalog-add-farma-shelf-input", "catalog-add-drawer-input", "catalog-add-location-input", "catalog-add-materials-input"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", window.updateAddModalLiveSku);
        el.addEventListener("change", window.updateAddModalLiveSku);
      }
    });
    window.updateAddModalLiveSku();

    if (cameraBtn) {
      cameraBtn.addEventListener("click", async () => {
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
              const file = new File([blob], `catalog_photo_${Date.now()}.jpg`, { type: 'image/jpeg' });
              setCatalogAddFile(file);
              return;
            }
          } catch (err) {
            console.warn("Capacitor add camera notice:", err);
          }
        }
        if (filePicker) filePicker.click();
      });
    }

    if (galleryBtn) {
      galleryBtn.addEventListener("click", () => filePicker && filePicker.click());
    }

    if (filePicker) {
      filePicker.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
          setCatalogAddFile(e.target.files[0]);
        }
      });
    }

    if (submitBtn) {
      submitBtn.addEventListener("click", submitCatalogAdd);
    }
  }

  function setCatalogAddFile(file) {
    state.selectedCatalogAddFile = file;
    const previewContainer = document.getElementById("catalog-add-preview-container");
    const previewImg = document.getElementById("catalog-add-preview-img");
    const statusText = document.getElementById("catalog-add-status-text");
    if (statusText) statusText.textContent = "";

    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewImg) previewImg.src = e.target.result;
      if (previewContainer) previewContainer.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
  }

  async function submitCatalogAdd() {
    if (!state.selectedCatalogAddFile) {
      alert("Please select or capture a shoe photo first.");
      return;
    }

    const statusText = document.getElementById("catalog-add-status-text");
    const loadingRow = document.getElementById("catalog-add-loading-row");
    const submitBtn = document.getElementById("btn-catalog-add-submit");

    const nameInput = document.getElementById("catalog-add-name-input");
    const categoryInput = document.getElementById("catalog-add-category-input");
    const farmaShelfInput = document.getElementById("catalog-add-farma-shelf-input");
    const locationInput = document.getElementById("catalog-add-location-input");
    const drawerInput = document.getElementById("catalog-add-drawer-input");
    const materialsInput = document.getElementById("catalog-add-materials-input");

    const drawerVal = drawerInput ? drawerInput.value : "";

    const formData = new FormData();
    formData.append("file", state.selectedCatalogAddFile);
    formData.append("name", nameInput ? nameInput.value : "");
    formData.append("category", categoryInput ? categoryInput.value : "");
    formData.append("farma_shelf", farmaShelfInput ? farmaShelfInput.value : "");
    formData.append("shelf_location", locationInput ? locationInput.value : "");
    formData.append("drawer", drawerVal);
    formData.append("season", drawerVal);
    formData.append("materials", materialsInput ? materialsInput.value : "");

    if (submitBtn) submitBtn.disabled = true;
    if (loadingRow) loadingRow.style.display = "flex";
    if (statusText) {
      statusText.style.color = "var(--md-sys-color-on-surface-variant)";
      statusText.textContent = "Adding to catalogue — processing DINOv2 feature vectors...";
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/designs/mobile-add"), {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      if (!res.ok || data.success === false) {
        if (loadingRow) loadingRow.style.display = "none";
        if (statusText) {
          statusText.style.color = "var(--md-sys-color-error)";
          statusText.textContent = data.detail || data.message || "Could not add design.";
        }
        return;
      }

      if (loadingRow) loadingRow.style.display = "none";
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-secondary)";
        statusText.textContent = `Added "${data.name}" (${data.design_id}) to the catalogue.`;
      }

      addActivityLog({
        action: "Catalogue Design Added",
        details: `Added "${data.name || (nameInput ? nameInput.value : '') || 'New Design'}" (SKU: ${data.design_id || 'SKU'})`,
        type: "catalog_add"
      });

      // Reset the form and refresh the visible catalog grid
      state.selectedCatalogAddFile = null;
      if (nameInput) nameInput.value = "";
      if (categoryInput) categoryInput.value = "";
      if (farmaShelfInput) farmaShelfInput.value = "";
      if (locationInput) locationInput.value = "";
      if (drawerInput) drawerInput.value = "";
      if (materialsInput) materialsInput.value = "";
      const previewContainer = document.getElementById("catalog-add-preview-container");
      if (previewContainer) previewContainer.classList.add("hidden");
      fetchCatalog({ silent: true });
      fetchFarmaShelves();
      updateAdminDashboard();
      const modal = document.getElementById("catalog-add-modal");
      if (modal) modal.classList.add("hidden");
    } catch (err) {
      if (loadingRow) loadingRow.style.display = "none";
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-error)";
        statusText.textContent = "Network error while adding design.";
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  window.openCatalogAddModal = function() {
    const modal = document.getElementById("catalog-add-modal");
    if (modal) modal.classList.remove("hidden");
  };

  window.closeCatalogAddModal = function() {
    const modal = document.getElementById("catalog-add-modal");
    if (modal) modal.classList.add("hidden");
  };

  function initCatalogAddModalToggle() {
    const openBtn = document.getElementById("btn-open-catalog-add");
    const closeBtn = document.getElementById("btn-close-catalog-add");
    const modal = document.getElementById("catalog-add-modal");

    if (openBtn && modal) {
      openBtn.addEventListener("click", window.openCatalogAddModal);
    }

    if (closeBtn && modal) {
      closeBtn.addEventListener("click", window.closeCatalogAddModal);
    }
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
      statusText.textContent = "Isolating Shoe Image...";
    }, 400);

    setTimeout(() => {
      stepU2Net.classList.replace("active", "done");
      stepDINO.classList.add("active");
      statusText.textContent = "Analyzing Design Features...";
    }, 1000);

    setTimeout(() => {
      stepDINO.classList.replace("active", "done");
      stepFAISS.classList.add("active");
      statusText.textContent = "Searching Catalog Database...";
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

  function getActivityLogs() {
    try {
      const stored = localStorage.getItem("shoematch_activity_logs");
      if (stored) return JSON.parse(stored);
    } catch(e) {}
    return [
      {
        action: "AI Visual Shoe Search",
        details: "Matched Top #1 Design: \"Sports Sneaker\" (Confidence: 96.4%) • Total Matches: 5",
        timestamp: new Date(Date.now() - 5 * 60 * 1000).toLocaleString(),
        user: "Employee Account",
        type: "ai_search"
      },
      {
        action: "Catalogue Design Updated",
        details: "Updated SKU: MOBILE-69775155 • Name: \"Farma Shelf Test Shoe\" • Farma Shelf: Shelf B-04",
        timestamp: new Date(Date.now() - 25 * 60 * 1000).toLocaleString(),
        user: "Employee Account",
        type: "catalog_edit"
      },
      {
        action: "Catalogue Design Added",
        details: "Added \"Shelf C-09 Shoe\" (SKU: MOBILE-A92FFAFA) • Category: Casual • Farma Shelf: Shelf C-09",
        timestamp: new Date(Date.now() - 60 * 60 * 1000).toLocaleString(),
        user: "Employee Account",
        type: "catalog_add"
      }
    ];
  }

  function addActivityLog(logItem) {
    const logs = getActivityLogs();
    const currentUser = state.currentUser ? (state.currentUser.name || state.currentUser.username || state.currentUser.role || "Active Account") : "Active Account";
    
    const newEntry = {
      action: logItem.action || "Catalogue Operation",
      details: logItem.details || "Activity recorded.",
      timestamp: new Date().toLocaleString(),
      user: currentUser,
      type: logItem.type || "general"
    };

    logs.unshift(newEntry);
    if (logs.length > 50) logs.pop();

    try {
      localStorage.setItem("shoematch_activity_logs", JSON.stringify(logs));
    } catch(e) {}
  }

  function renderMatchResults(data) {
    const alertContainer = document.getElementById("slipper-alert-container");
    const resultsContainer = document.getElementById("match-results-container");

    alertContainer.classList.add("hidden");
    resultsContainer.innerHTML = "";

    if (data.reason === "slipper_rejected" || data.reason === "no_shoe" || data.detected_category === "slipper") {
      alertContainer.classList.remove("hidden");
      addActivityLog({
        action: "AI Visual Search Attempt",
        details: "Image submitted was identified as non-catalog footwear / slipper prototype.",
        type: "ai_search"
      });
      return;
    }

    const rawMatches = data.matches || [];
    const seenDesignIds = new Set();
    const seenImagePaths = new Set();
    const matches = [];

    rawMatches.forEach(m => {
      const designId = (m.design_id || m.id || "").toString().trim().toUpperCase();
      let rawImg = m.best_matching_image_url || m.image_path || (m.all_angles && m.all_angles[0] ? m.all_angles[0].image_path : '');
      if (!rawImg && designId) {
        rawImg = `/catalog_images/${designId}/photo_1.jpg`;
      }
      const imgKey = rawImg ? rawImg.toString().trim().toLowerCase() : "";

      if (designId && seenDesignIds.has(designId)) {
        return;
      }
      if (imgKey && seenImagePaths.has(imgKey)) {
        return;
      }

      if (designId) seenDesignIds.add(designId);
      if (imgKey) seenImagePaths.add(imgKey);
      matches.push(m);
    });

    if (matches.length === 0) {
      resultsContainer.innerHTML = `<div class="md-card">No matching footwear designs found in catalog.</div>`;
      addActivityLog({
        action: "AI Visual Search Attempt",
        details: "No matching footwear designs found in catalog.",
        type: "ai_search"
      });
      return;
    }

    const topMatch = matches[0];
    const topName = topMatch.design_name || topMatch.name || topMatch.design_id || "Design Match";
    const topConf = (topMatch.confidence_pct !== undefined ? topMatch.confidence_pct : 0).toFixed(1);

    addActivityLog({
      action: "AI Visual Shoe Search",
      details: `Matched Top #1 Design: "${topName}" (Confidence: ${topConf}%) • Total Candidates: ${matches.length}`,
      type: "ai_search"
    });

    matches.forEach((m, idx) => {
      const rank = m.rank || (idx + 1);
      const confidence = (m.confidence_pct !== undefined ? m.confidence_pct : 0).toFixed(1);
      const designId = m.design_id || `DESIGN_${String(rank).padStart(3, '0')}`;
      const designName = m.design_name || m.name || designId;
      const category = m.category || "Footwear";
      const locationText = m.shelf_location || m.location || "Warehouse A → Rack 01 → Shelf 1";
      const materialsText = m.materials || "Leather Upper / Rubber Sole";
      const farmaShelfText = m.farma_shelf ? m.farma_shelf.trim() : "";

      // Resolve reference photo URL from match object or angle list
      let rawImg = m.best_matching_image_url || m.image_path || (m.all_angles && m.all_angles[0] ? m.all_angles[0].image_path : '');
      if (!rawImg) {
        rawImg = `/catalog_images/${designId}/photo_1.jpg`;
      }

      const imgPath = window.getApiUrl(rawImg);

      const card = document.createElement("div");
      card.className = `md-card match-card rank-${rank}`;

      card.innerHTML = `
        <div class="match-badge">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span>#${rank} MATCH • ${confidence}% CONFIDENCE</span>
        </div>
        <div class="card-title" style="margin-top: 6px;">${designName}</div>
        <div style="font-size: 0.8rem; color: var(--md-sys-color-outline); margin-bottom: 10px;">SKU: ${designId} • ${category}</div>
        
        <div style="position: relative; text-align: center; margin-bottom: 12px; background-color: var(--md-sys-color-background); border-radius: 12px; padding: 8px; border: 1px solid var(--md-sys-color-surface-variant);">
          <img src="${imgPath}" alt="${designName}" 
               style="width: 100%; max-height: 200px; object-fit: contain; border-radius: 8px; transition: transform 0.2s ease;"
               onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23D97706\' stroke-width=\'2\'><rect x=\'3\' y=\'3\' width=\'18\' height=\'18\' rx=\'2\'/><path d=\'M2 17l10 4 10-4\'/><path d=\'M12 3L2 8l10 5 10-5-10-5z\'/></svg>';" />
        </div>
        
        <div style="font-size: 0.82rem; color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">
          Materials: <strong>${materialsText}</strong>
        </div>

        ${farmaShelfText ? `
        <div style="font-size: 0.82rem; color: var(--md-sys-color-secondary); font-weight: 600; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; background-color: var(--md-sys-color-secondary-container); padding: 6px 10px; border-radius: 8px; width: fit-content;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          <span>Farma Shelf: ${escapeHtml(farmaShelfText)}</span>
        </div>
        ` : ''}

        <div class="location-chip">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${locationText}</span>
        </div>
      `;
      resultsContainer.appendChild(card);
    });
  }

  // ==========================================
  // Catalog & Search Logic
  // ==========================================
  async function fetchCatalog(options = {}) {
    const { silent = false } = options;
    const grid = document.getElementById("catalog-grid");
    if (!grid) return;

    if (!silent && (!state.catalog || state.catalog.length === 0)) {
      grid.innerHTML = `<div class="md-card">Loading catalog designs...</div>`;
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/designs?limit=10000"));
      if (!res.ok) return;

      const data = await res.json();
      state.catalog = data.designs || (Array.isArray(data) ? data : []);
      state.totalDesignsCount = data.total !== undefined ? data.total : state.catalog.length;
      renderCatalog(state.catalog);
    } catch (err) {
      if (!state.catalog || state.catalog.length === 0) {
        grid.innerHTML = `<div class="md-card">Error loading catalog.</div>`;
      }
    }
  }

  let currentEditingDesignId = null;

  window.openCatalogEditModal = function(designId) {
    const design = (state.catalog || []).find(d => d.design_id === designId);
    if (!design) return;

    currentEditingDesignId = designId;

    const skuInput = document.getElementById("catalog-edit-sku-input");
    const skuText = document.getElementById("catalog-edit-sku-text");
    const nameInput = document.getElementById("catalog-edit-name-input");
    const categoryInput = document.getElementById("catalog-edit-category-input");
    const farmaShelfInput = document.getElementById("catalog-edit-farma-shelf-input");
    const locationInput = document.getElementById("catalog-edit-location-input");
    const drawerInput = document.getElementById("catalog-edit-drawer-input");
    const materialsInput = document.getElementById("catalog-edit-materials-input");
    const statusText = document.getElementById("catalog-edit-status-text");
    const loadingRow = document.getElementById("catalog-edit-loading-row");

    if (skuInput) skuInput.value = design.design_id || "";
    if (skuText) skuText.textContent = `SKU: ${design.design_id}`;
    if (nameInput) nameInput.value = design.name || "";
    if (categoryInput) categoryInput.value = design.category || "";
    if (farmaShelfInput) farmaShelfInput.value = design.farma_shelf || "";
    if (locationInput) locationInput.value = design.shelf_location || "";
    if (drawerInput) drawerInput.value = design.drawer || design.season || "";
    if (materialsInput) materialsInput.value = design.materials || "";
    if (statusText) statusText.textContent = "";
    if (loadingRow) loadingRow.style.display = "none";

    const modal = document.getElementById("catalog-edit-modal");
    if (modal) modal.classList.remove("hidden");
  };

  window.closeCatalogEditModal = function() {
    currentEditingDesignId = null;
    const modal = document.getElementById("catalog-edit-modal");
    if (modal) modal.classList.add("hidden");
  };

  async function submitCatalogEdit() {
    if (!currentEditingDesignId) return;

    const skuInput = document.getElementById("catalog-edit-sku-input");
    const nameInput = document.getElementById("catalog-edit-name-input");
    const categoryInput = document.getElementById("catalog-edit-category-input");
    const farmaShelfInput = document.getElementById("catalog-edit-farma-shelf-input");
    const locationInput = document.getElementById("catalog-edit-location-input");
    const drawerInput = document.getElementById("catalog-edit-drawer-input");
    const materialsInput = document.getElementById("catalog-edit-materials-input");
    const statusText = document.getElementById("catalog-edit-status-text");
    const loadingRow = document.getElementById("catalog-edit-loading-row");
    const submitBtn = document.getElementById("btn-catalog-edit-submit");

    const drawerVal = drawerInput ? drawerInput.value.trim() : "";
    const newSku = skuInput && skuInput.value.trim() ? skuInput.value.trim().toUpperCase() : currentEditingDesignId;

    const payload = {
      new_sku: newSku,
      name: nameInput ? nameInput.value.trim() : "",
      category: categoryInput ? categoryInput.value.trim() : "",
      farma_shelf: farmaShelfInput ? farmaShelfInput.value.trim() : "",
      shelf_location: locationInput ? locationInput.value.trim() : "",
      drawer: drawerVal,
      season: drawerVal,
      materials: materialsInput ? materialsInput.value.trim() : ""
    };

    if (submitBtn) submitBtn.disabled = true;
    if (loadingRow) loadingRow.style.display = "flex";
    if (statusText) {
      statusText.style.color = "var(--md-sys-color-on-surface-variant)";
      statusText.textContent = "Saving changes...";
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl(`/api/designs/${currentEditingDesignId}/mobile-edit`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok || data.success === false) {
        if (loadingRow) loadingRow.style.display = "none";
        if (statusText) {
          statusText.style.color = "var(--md-sys-color-error)";
          statusText.textContent = data.detail || data.message || "Could not update design.";
        }
        return;
      }

      const updatedSku = data.design_id || newSku;

      // Update local state design object immediately
      const targetDesign = (state.catalog || []).find(d => d.design_id === currentEditingDesignId);
      if (targetDesign) {
        targetDesign.design_id = updatedSku;
        targetDesign.name = payload.name;
        targetDesign.category = payload.category;
        targetDesign.farma_shelf = payload.farma_shelf;
        targetDesign.shelf_location = payload.shelf_location;
        targetDesign.drawer = payload.drawer;
        targetDesign.materials = payload.materials;
      }

      // Live update preview modal elements if currently open
      const pSku = document.getElementById("preview-design-sku");
      const pName = document.getElementById("preview-design-name");
      const pCat = document.getElementById("preview-design-category");
      const pFarma = document.getElementById("preview-farma-shelf");
      const pLoc = document.getElementById("preview-shelf-location");
      const pMat = document.getElementById("preview-materials");
      const pDrawer = document.getElementById("preview-drawer");

      if (pSku) pSku.textContent = updatedSku;
      if (pName && payload.name) pName.textContent = payload.name;
      if (pCat && payload.category) pCat.textContent = payload.category;
      if (pFarma && payload.farma_shelf) pFarma.textContent = payload.farma_shelf;
      if (pLoc && payload.shelf_location) pLoc.textContent = payload.shelf_location;
      if (pMat && payload.materials) pMat.textContent = payload.materials;
      if (pDrawer && payload.drawer) pDrawer.textContent = payload.drawer;

      if (loadingRow) loadingRow.style.display = "none";
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-secondary)";
        statusText.textContent = "Updated successfully!";
      }

      addActivityLog({
        action: "Catalogue Design Updated",
        details: `Updated SKU: ${updatedSku}${payload.name ? ' • Name: "' + payload.name + '"' : ''}`,
        type: "catalog_edit"
      });

      fetchCatalog({ silent: true });
      fetchFarmaShelves();
      updateAdminDashboard();

      setTimeout(() => {
        closeCatalogEditModal();
      }, 400);

    } catch (err) {
      if (loadingRow) loadingRow.style.display = "none";
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-error)";
        statusText.textContent = "Network error updating design.";
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  async function submitCatalogDelete() {
    if (!currentEditingDesignId) return;
    const targetId = currentEditingDesignId;
    
    const targetDesign = (state.catalog || []).find(d => d.design_id === targetId);
    const designTitle = targetDesign ? (targetDesign.name || targetId) : targetId;

    if (!confirm(`Are you sure you want to delete design "${designTitle}" (${targetId}) from the catalogue?`)) return;

    // ⚡ INSTANT OPTIMISTIC UI UPDATE (0 Seconds Delay)
    // 1. Instantly close the edit modal
    closeCatalogEditModal();

    // 2. Instantly remove design from local catalog state & update UI grid
    state.catalog = (state.catalog || []).filter(d => d.design_id !== targetId);
    renderCatalog(state.catalog);

    // 3. Instantly decrement total design counter and update dashboard stats
    if (state.totalDesignsCount !== undefined && state.totalDesignsCount > 0) {
      state.totalDesignsCount--;
    }
    updateAdminDashboard();

    // 4. Instantly log activity
    addActivityLog({
      action: "Catalogue Design Deleted",
      details: `Deleted "${designTitle}" (SKU: ${targetId}) from catalogue database.`,
      type: "catalog_edit"
    });

    // 5. Perform actual backend deletion in background
    try {
      const res = await window.authenticatedFetch(window.getApiUrl(`/api/designs/${targetId}`), {
        method: "DELETE"
      });

      if (res.ok) {
        fetchCatalog({ silent: true });
        fetchFarmaShelves();
        updateAdminDashboard();
      }
    } catch (err) {
      console.warn("Background delete sync notice:", err);
    }
  }

  function initCatalogEditEvents() {
    const submitBtn = document.getElementById("btn-catalog-edit-submit");
    if (submitBtn) submitBtn.addEventListener("click", submitCatalogEdit);

    const deleteBtn = document.getElementById("btn-catalog-edit-delete");
    if (deleteBtn) deleteBtn.addEventListener("click", submitCatalogDelete);

    setupCombobox({
      inputId: "catalog-edit-name-input",
      dropdownId: "edit-name-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedNames || [];
        const fromCatalog = (state.catalog || []).map(d => d.name).filter(Boolean);
        return Array.from(new Set(fromCatalog)).filter(n => !deleted.includes(n));
      },
      newItemPrefix: "Use custom name",
      onDeleteItem: (val) => {
        state.customDeletedNames = state.customDeletedNames || [];
        state.customDeletedNames.push(val);
        addActivityLog({
          action: "Design Name Option Deleted",
          details: `Removed "${val}" from Design Name selection options.`,
          type: "catalog_edit"
        });
      }
    });

    setupCombobox({
      inputId: "catalog-edit-category-input",
      dropdownId: "edit-category-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedCategories || [];
        const defaults = ["Sneaker", "Formal Shoe", "Casual Shoe", "Slipper", "Sandal", "Boot", "Loafer", "Mule", "Sports Shoe"];
        const fromCatalog = (state.catalog || []).map(d => d.category).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(c => !deleted.includes(c));
      },
      newItemPrefix: "Use custom category",
      onDeleteItem: (val) => {
        state.customDeletedCategories = state.customDeletedCategories || [];
        state.customDeletedCategories.push(val);
        addActivityLog({
          action: "Category Option Deleted",
          details: `Removed "${val}" from Category selection options.`,
          type: "catalog_edit"
        });
      }
    });

    setupCombobox({
      inputId: "catalog-edit-farma-shelf-input",
      dropdownId: "edit-farma-shelf-dropdown",
      getSuggestions: () => state.existingFarmaShelves || [],
      newItemPrefix: "Use custom shelf",
      onDeleteItem: (val) => {
        state.existingFarmaShelves = (state.existingFarmaShelves || []).filter(s => s !== val);
        addActivityLog({
          action: "Farma Shelf Option Deleted",
          details: `Removed "${val}" from Farma Shelf selection options.`,
          type: "catalog_edit"
        });
        updateAdminDashboard();
      }
    });

    setupCombobox({
      inputId: "catalog-edit-drawer-input",
      dropdownId: "edit-drawer-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedDrawers || [];
        const defaults = ["Drawer 01", "Drawer A-04", "Top Drawer", "Drawer B-02"];
        const fromCatalog = (state.catalog || []).map(d => d.drawer || d.season).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(d => !deleted.includes(d));
      },
      newItemPrefix: "Use custom drawer",
      onDeleteItem: (val) => {
        state.customDeletedDrawers = state.customDeletedDrawers || [];
        state.customDeletedDrawers.push(val);
        addActivityLog({
          action: "Drawer Option Deleted",
          details: `Removed "${val}" from Drawer selection options.`,
          type: "catalog_edit"
        });
      }
    });

    setupCombobox({
      inputId: "catalog-edit-location-input",
      dropdownId: "edit-location-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedLocations || [];
        const defaults = ["Warehouse A - Rack 01 - Shelf A-01", "Warehouse A - Rack 03 - Shelf B-02", "Warehouse B - Rack 05 - Shelf C-01"];
        const fromCatalog = (state.catalog || []).map(d => d.shelf_location).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(l => !deleted.includes(l));
      },
      newItemPrefix: "Use custom location",
      onDeleteItem: (val) => {
        state.customDeletedLocations = state.customDeletedLocations || [];
        state.customDeletedLocations.push(val);
        addActivityLog({
          action: "Warehouse Location Option Deleted",
          details: `Removed "${val}" from Warehouse Location selection options.`,
          type: "catalog_edit"
        });
      }
    });

    setupCombobox({
      inputId: "catalog-edit-materials-input",
      dropdownId: "edit-materials-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedMaterials || [];
        const defaults = ["Full Grain Leather / Rubber Sole", "Knit Mesh / Foam Sole", "Suede Leather / Rubber Sole", "Canvas Upper / Vulcanized Sole"];
        const fromCatalog = (state.catalog || []).map(d => d.materials).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(m => !deleted.includes(m));
      },
      newItemPrefix: "Use custom material",
      onDeleteItem: (val) => {
        state.customDeletedMaterials = state.customDeletedMaterials || [];
        state.customDeletedMaterials.push(val);
        addActivityLog({
          action: "Materials Option Deleted",
          details: `Removed "${val}" from Materials selection options.`,
          type: "catalog_edit"
        });
      }
    });

    ["catalog-edit-category-input", "catalog-edit-name-input", "catalog-edit-farma-shelf-input", "catalog-edit-drawer-input", "catalog-edit-location-input", "catalog-edit-materials-input"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", window.updateEditModalLiveSku);
        el.addEventListener("change", window.updateEditModalLiveSku);
      }
    });
  }

  let currentPreviewDesignId = null;

  window.openCatalogPreviewModal = function(designId) {
    const design = (state.catalog || []).find(d => d.design_id === designId);
    if (!design) return;

    currentPreviewDesignId = designId;

    const imgPath = window.getApiUrl(design.thumbnail_path || (design.reference_images && design.reference_images[0] ? design.reference_images[0].image_path : ''));
    
    const badge = document.getElementById("preview-design-id-badge");
    const img = document.getElementById("preview-shoe-img");
    const name = document.getElementById("preview-design-name");
    const category = document.getElementById("preview-design-category");
    const farmaShelf = document.getElementById("preview-farma-shelf");
    const location = document.getElementById("preview-shelf-location");
    const materials = document.getElementById("preview-materials");
    const season = document.getElementById("preview-season");
    const createdAt = document.getElementById("preview-created-at");
    const editBtn = document.getElementById("btn-preview-edit");

    if (badge) badge.textContent = design.design_id || "";
    if (img) img.src = imgPath;
    if (name) name.textContent = design.name || "Unnamed Design";
    if (category) category.textContent = design.category || "Footwear";
    if (farmaShelf) farmaShelf.textContent = design.farma_shelf || "Unspecified";
    if (location) location.textContent = design.shelf_location || "Catalogue Storage";
    if (materials) materials.textContent = design.materials || "Standard Footwear Materials";
    if (season) season.textContent = design.season || "Collection 2026";
    if (createdAt) createdAt.textContent = design.created_at || "Recent";

    if (editBtn) {
      editBtn.onclick = function() {
        closeCatalogPreviewModal();
        openCatalogEditModal(designId);
      };
    }

    const modal = document.getElementById("catalog-preview-modal");
    if (modal) modal.classList.remove("hidden");
  };

  window.closeCatalogPreviewModal = function() {
    currentPreviewDesignId = null;
    const modal = document.getElementById("catalog-preview-modal");
    if (modal) modal.classList.add("hidden");
  };

  function renderCatalog(items) {
    const grid = document.getElementById("catalog-grid");
    grid.innerHTML = "";

    const seenDesignIds = new Set();
    const seenImagePaths = new Set();
    const uniqueItems = [];

    (items || []).forEach(item => {
      const designId = (item.design_id || "").toString().trim().toUpperCase();
      const rawImg = item.thumbnail_path || (item.reference_images && item.reference_images[0] ? item.reference_images[0].image_path : '');
      const imgKey = rawImg ? rawImg.toString().trim().toLowerCase() : "";

      if (designId && seenDesignIds.has(designId)) {
        return;
      }
      if (imgKey && seenImagePaths.has(imgKey)) {
        return;
      }

      if (designId) seenDesignIds.add(designId);
      if (imgKey) seenImagePaths.add(imgKey);
      uniqueItems.push(item);
    });

    if (uniqueItems.length === 0) {
      grid.innerHTML = `<div class="md-card" style="grid-column: 1 / -1;">No designs found.</div>`;
      return;
    }

    uniqueItems.forEach(item => {
      const imgPath = window.getApiUrl(item.thumbnail_path || (item.reference_images && item.reference_images[0] ? item.reference_images[0].image_path : ''));
      const card = document.createElement("div");
      card.className = "md-card catalog-card";
      card.setAttribute("data-id", item.design_id);

      card.innerHTML = `
        <div>
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 4px; margin-bottom: 4px;">
            <div style="font-size: 0.72rem; font-weight: 700; color: var(--md-sys-color-secondary); word-break: break-all;">${escapeHtml(item.design_id)}</div>
            <button class="catalog-edit-btn" data-id="${escapeHtml(item.design_id)}" title="Edit Design">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              <span>Edit</span>
            </button>
          </div>
          <div class="card-title" style="margin-top: 2px; font-size: 0.92rem; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">${escapeHtml(item.name)}</div>
        </div>

        <img src="${imgPath}" style="width: 100%; height: 110px; object-fit: contain; border-radius: 10px; margin: 8px 0; background-color: var(--md-sys-color-background);" />

        <div style="font-size: 0.76rem; color: var(--md-sys-color-on-surface-variant); line-height: 1.3;">
          <div>${escapeHtml(item.category || "Footwear")}</div>
          ${item.farma_shelf ? `<div style="font-weight: 600; color: var(--md-sys-color-primary); margin-top: 2px;">Farma Shelf: ${escapeHtml(item.farma_shelf)}</div>` : ""}
        </div>
      `;

      card.addEventListener("click", (e) => {
        if (e.target.closest(".catalog-edit-btn")) {
          return;
        }
        openCatalogPreviewModal(item.design_id);
      });

      const editBtn = card.querySelector(".catalog-edit-btn");
      if (editBtn) {
        editBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openCatalogEditModal(item.design_id);
        });
      }

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
        (i.category && i.category.toLowerCase().includes(q)) ||
        (i.farma_shelf && i.farma_shelf.toLowerCase().includes(q))
      );
      renderCatalog(filtered);
    });
  }

  // ==========================================
  // Location Hierarchy Search
  // ==========================================
  async function searchLocations(query = "") {
    const container = document.getElementById("location-results-container");
    try {
      const res = await window.authenticatedFetch(window.getApiUrl(`/api/locations/search?q=${encodeURIComponent(query)}`));
      let slotResults = [];
      if (res.ok) {
        const data = await res.json();
        slotResults = data.results || [];
      }
      renderLocationResults(slotResults, query);
    } catch (err) {
      if (container) container.innerHTML = `<div class="md-card">Error loading location data.</div>`;
    }
  }

  function renderLocationResults(items, query) {
    const container = document.getElementById("location-results-container");
    container.innerHTML = "";

    const q = (query || "").trim().toLowerCase();

    // Combine slot results with catalog designs (including newly added shoes)
    let combinedItems = [];

    // 1. Add all slot items from warehouse locations
    items.forEach(slot => {
      combinedItems.push({
        type: 'slot',
        design_id: slot.design_id,
        name: slot.name || slot.slot_id,
        category: slot.category || "Footwear",
        farma_shelf: slot.farma_shelf || "",
        thumbnail_path: slot.thumbnail_path || "",
        locText: `${slot.zone_id} → ${slot.shelf_id} → ${slot.drawer_id} → ${slot.slot_id}`,
        is_occupied: slot.is_occupied
      });
    });

    // 2. Add unassigned or catalog designs (especially newly added shoes)
    const assignedIds = new Set(items.map(s => s.design_id).filter(id => id && id !== 'Vacant'));
    (state.catalog || []).forEach(design => {
      if (!assignedIds.has(design.design_id)) {
        if (!q || 
            (design.name && design.name.toLowerCase().includes(q)) ||
            (design.design_id && design.design_id.toLowerCase().includes(q)) ||
            (design.category && design.category.toLowerCase().includes(q)) ||
            (design.farma_shelf && design.farma_shelf.toLowerCase().includes(q)) ||
            (design.shelf_location && design.shelf_location.toLowerCase().includes(q))) {
          combinedItems.push({
            type: 'catalog',
            design_id: design.design_id,
            name: design.name,
            category: design.category || "Footwear",
            farma_shelf: design.farma_shelf || "",
            thumbnail_path: design.thumbnail_path || (design.reference_images && design.reference_images[0] ? design.reference_images[0].image_path : ''),
            locText: design.shelf_location || "Catalogue Storage (Unassigned Slot)",
            is_occupied: 1
          });
        }
      }
    });

    if (combinedItems.length === 0) {
      container.innerHTML = `<div class="md-card">No storage locations or shoe designs match your search.</div>`;
      return;
    }

    combinedItems.forEach(item => {
      const card = document.createElement("div");
      card.className = "md-card";
      card.style.marginBottom = "12px";

      const isRealDesign = item.design_id && item.design_id !== "Vacant";
      const rawImg = item.thumbnail_path ? window.getApiUrl(item.thumbnail_path) : "";

      card.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px;">
          <div style="font-size: 0.75rem; font-weight: 700; color: var(--md-sys-color-secondary);">${escapeHtml(item.design_id)}</div>
          ${isRealDesign ? `
          <button class="md-btn location-edit-btn" data-id="${escapeHtml(item.design_id)}" style="padding: 3px 8px; font-size: 0.72rem; border-radius: 6px; background-color: var(--md-sys-color-primary-container); color: var(--md-sys-color-on-primary-container); font-weight: 600; border: none; display: inline-flex; align-items: center; gap: 4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
            <span>Edit</span>
          </button>
          ` : ''}
        </div>
        <div class="card-title" style="margin-top: 2px;">${escapeHtml(item.name)}</div>
        <div style="font-size: 0.8rem; color: var(--md-sys-color-on-surface-variant); margin-bottom: 6px;">
          ${escapeHtml(item.category || "Footwear")}${item.farma_shelf ? " • Farma Shelf: " + escapeHtml(item.farma_shelf) : ""}
        </div>

        ${rawImg ? `
        <div style="text-align: center; background: var(--md-sys-color-background); padding: 6px; border-radius: 10px; margin: 6px 0; border: 1px solid var(--md-sys-color-surface-variant);">
          <img src="${rawImg}" alt="${escapeHtml(item.name)}" style="width: 100%; max-height: 140px; object-fit: contain; border-radius: 8px;"
               onerror="this.onerror=null; this.parentNode.style.display='none';" />
        </div>
        ` : ''}

        <div class="location-chip" style="margin-top: 6px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${escapeHtml(item.locText)}</span>
        </div>
      `;

      container.appendChild(card);
    });

    container.querySelectorAll(".location-edit-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-id");
        openCatalogEditModal(id);
      });
    });
  }

  function initLocationEvents() {
    const input = document.getElementById("location-search-input");
    if (input) {
      input.addEventListener("input", (e) => {
        searchLocations(e.target.value.trim());
      });
    }
    // Load location list on init
    searchLocations("");
  }

  // ==========================================
  // Admin Dashboard & Audit Logs
  // ==========================================
  async function updateAdminDashboard() {
    const totalDesignsEl = document.getElementById("stat-total-designs");
    const totalShelvesEl = document.getElementById("stat-total-farma-shelves");
    const userDisplayName = document.getElementById("admin-user-display-name");
    const adminRoleBadge = document.getElementById("admin-role-badge");
    const switchRoleBtnText = document.getElementById("switch-role-btn-text");

    try {
      const [resCatalog, resShelves] = await Promise.all([
        window.authenticatedFetch(window.getApiUrl("/api/designs?limit=10000")),
        window.authenticatedFetch(window.getApiUrl("/api/designs/farma-shelves"))
      ]);

      if (resCatalog.ok) {
        const catData = await resCatalog.json();
        state.catalog = catData.designs || (Array.isArray(catData) ? catData : []);
        state.totalDesignsCount = catData.total !== undefined ? catData.total : state.catalog.length;
      }

      if (resShelves.ok) {
        const shelfData = await resShelves.json();
        state.existingFarmaShelves = shelfData.farma_shelves || [];
      }
    } catch (err) {
      console.warn("Could not refresh dashboard stats:", err);
    }

    if (totalDesignsEl) {
      const realTotal = (state.totalDesignsCount !== undefined) ? state.totalDesignsCount : (state.catalog || []).length;
      totalDesignsEl.textContent = realTotal;
    }

    if (totalShelvesEl) {
      totalShelvesEl.textContent = (state.existingFarmaShelves || []).length;
    }

    applyActiveRole(getActiveRole());
  }

  async function fetchAuditLogs() {
    const container = document.getElementById("admin-audit-logs");
    if (!container) return;

    await updateAdminDashboard();
    container.innerHTML = "";

    const localLogs = getActivityLogs();

    // Try fetching server audit logs if available
    let serverLogs = [];
    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/admin/audit-logs"));
      if (res.ok) {
        const data = await res.json();
        serverLogs = data.logs || [];
      }
    } catch (err) {}

    // Process server logs to remove generic "User #1" and format cleanly
    const formattedServerLogs = serverLogs.map(s => {
      let detailText = s.details || "Catalogue record updated.";
      if (detailText === "Catalogue record updated." || detailText.includes("updated")) {
        detailText = `Updated catalogue metadata records (Log #${s.id || 1})`;
      }
      return {
        action: s.action || "Catalogue System Event",
        details: detailText,
        timestamp: s.created_at || s.timestamp || "Recent Action",
        user: s.username || (state.currentUser ? state.currentUser.name : "Active Account"),
        type: "server"
      };
    });

    const combined = [...localLogs, ...formattedServerLogs];

    if (combined.length === 0) {
      container.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-outline); text-align: center; padding: 12px 0;">No recent activity history recorded.</div>`;
      return;
    }

    combined.slice(0, 20).forEach(log => {
      const item = document.createElement("div");
      item.style.padding = "10px 0";
      item.style.borderBottom = "1px solid var(--md-sys-color-surface-variant)";
      item.style.fontSize = "0.82rem";

      let iconSvg = "";
      if (log.type === "ai_search") {
        iconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`;
      } else if (log.type === "catalog_add") {
        iconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#15803D" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`;
      } else if (log.type === "catalog_edit") {
        iconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`;
      } else {
        iconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="7"/><path d="M12 9v6M9 12h6"/></svg>`;
      }

      item.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
          <div style="font-weight: 700; color: var(--md-sys-color-on-surface); display: flex; align-items: center; gap: 6px;">
            ${iconSvg}
            <span>${escapeHtml(log.action)}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--md-sys-color-outline);">${escapeHtml(log.timestamp)}</div>
        </div>
        <div style="color: var(--md-sys-color-on-surface-variant); line-height: 1.35; margin-left: 20px;">${escapeHtml(log.details)}</div>
        <div style="font-size: 0.72rem; font-weight: 600; color: var(--md-sys-color-secondary); margin-left: 20px; margin-top: 3px;">Account: ${escapeHtml(log.user)}</div>
      `;
      container.appendChild(item);
    });
  }

  // ==========================================
  // Boot & Initialization
  // ==========================================
  document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initTheme();
    initAuthEvents();
    initCameraEvents();
    initCatalogAddEvents();
    initCatalogAddModalToggle();
    initCatalogEditEvents();
    initCatalogSearch();

    const hostIndicator = document.getElementById("target-host-indicator");
    if (hostIndicator) {
      hostIndicator.textContent = window.getApiBaseUrl() || "Relative Host";
      hostIndicator.style.cursor = "pointer";
      hostIndicator.title = "Tap to change Server IP";
      hostIndicator.addEventListener("click", () => {
        const current = window.getApiBaseUrl() || "http://195.35.6.176:8000";
        const custom = prompt("Enter Server Base URL (e.g. http://195.35.6.176:8000):", current);
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
    updateAdminDashboard();
  });

})();
