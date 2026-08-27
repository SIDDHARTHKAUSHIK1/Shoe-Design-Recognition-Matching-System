/**
 * ShoeMatch AI — Material Design 3 Native Mobile Application Logic
 */

(function () {
  'use strict';

  // Auto-Detect Screen Layout Engine
  function autoDetectScreenLayout() {
    try {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
      const vw = window.innerWidth * 0.01;
      document.documentElement.style.setProperty('--vw', `${vw}px`);
    } catch (e) {}
  }
  window.addEventListener('resize', autoDetectScreenLayout, { passive: true });
  window.addEventListener('orientationchange', autoDetectScreenLayout, { passive: true });
  autoDetectScreenLayout();

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

  window.openSwitchEmployeeModal = function () {
    renderSwitchEmployeeModalList();
    showModal("switch-employee-modal");
  };

  window.closeSwitchEmployeeModal = function () {
    hideModal("switch-employee-modal");
  };

  function renderSwitchEmployeeModalList() {
    const listContainer = document.getElementById("switch-employee-modal-list");
    if (!listContainer) return;

    const employees = (state.allUsers || []).filter(u => u.role === "employee");
    if (employees.length === 0) {
      listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-outline); text-align: center; padding: 12px 0;">No employee accounts found. Create one in User Management.</div>`;
      return;
    }

    listContainer.innerHTML = "";
    employees.forEach(emp => {
      const item = document.createElement("div");
      item.style.cssText = "display: flex; align-items: center; justify-content: space-between; background: var(--md-sys-color-background); padding: 10px 12px; border-radius: 12px; border: 1px solid var(--md-sys-color-surface-variant); cursor: pointer;";
      item.innerHTML = `
        <div>
          <div style="font-size: 0.86rem; font-weight: 700; color: var(--md-sys-color-on-surface);">${escapeHtml(emp.full_name || emp.username)}</div>
          <div style="font-size: 0.76rem; color: var(--md-sys-color-secondary);">@${escapeHtml(emp.username)}</div>
        </div>
        <button class="md-btn" style="padding: 6px 12px; font-size: 0.76rem; background-color: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); width: auto;">Select View</button>
      `;
      item.addEventListener("click", () => {
        window.closeSwitchEmployeeModal();
        window.switchToEmployeeAccount(emp);
      });
      listContainer.appendChild(item);
    });
  }

  function checkUserCanDelete() {
    if (getActiveRole() === "admin") return true;
    const activeUser = state.viewingEmployeeUser || state.user;
    if (!activeUser) return false;
    return activeUser.can_delete === 1 || activeUser.can_delete === true || activeUser.can_delete === "1";
  }

  function applyActiveRole(role) {
    const cleanRole = (role || "").toLowerCase() === "employee" ? "employee" : "admin";
    state.currentRole = cleanRole;
    localStorage.setItem("shoematch_active_role", cleanRole);

    if (state.user && state.user.role === "admin") {
      state.isPrimaryAdmin = true;
    }
    const isPrimaryAdmin = (state.user && state.user.role === "admin") || state.isPrimaryAdmin || false;

    const headerBadge = document.getElementById("role-badge");
    if (headerBadge) {
      headerBadge.textContent = cleanRole === "admin" ? "Admin" : "Employee";
    }

    const adminNavTab = document.getElementById("nav-tab-admin");
    if (adminNavTab) {
      adminNavTab.classList.remove("hidden");
    }
    const adminNavTabLabel = document.getElementById("nav-tab-admin-label") || (adminNavTab ? adminNavTab.querySelector(".nav-tab-label") : null);
    if (adminNavTabLabel) {
      adminNavTabLabel.textContent = cleanRole === "admin" ? "Admin" : "Employee";
    }

    const userDisplayName = document.getElementById("admin-user-display-name");
    const adminRoleBadge = document.getElementById("admin-role-badge");

    if (userDisplayName) {
      if (cleanRole === "admin") {
        userDisplayName.textContent = "Admin Account";
      } else if (state.viewingEmployeeUser) {
        userDisplayName.textContent = `Viewing Account: ${state.viewingEmployeeUser.full_name || state.viewingEmployeeUser.username}`;
      } else {
        userDisplayName.textContent = "Employee Account View";
      }
    }

    if (adminRoleBadge) {
      adminRoleBadge.textContent = cleanRole === "admin" ? "Admin" : "Employee View";
    }

    const switchContainer = document.getElementById("switch-role-container");
    const openModalBtn = document.getElementById("btn-open-switch-employee-modal");
    const returnAdminBtn = document.getElementById("btn-return-to-admin");

    if (switchContainer) {
      switchContainer.style.display = isPrimaryAdmin ? "block" : "none";
    }

    if (isPrimaryAdmin) {
      if (cleanRole === "admin") {
        if (openModalBtn) openModalBtn.classList.remove("hidden");
        if (returnAdminBtn) returnAdminBtn.classList.add("hidden");
      } else {
        if (openModalBtn) openModalBtn.classList.add("hidden");
        if (returnAdminBtn) returnAdminBtn.classList.remove("hidden");
      }
    }

    const deleteBtn = document.getElementById("btn-catalog-edit-delete");
    if (deleteBtn) {
      deleteBtn.style.display = checkUserCanDelete() ? "inline-flex" : "none";
    }

    const userManagementCard = document.getElementById("admin-user-management-card");
    if (userManagementCard) {
      userManagementCard.style.display = cleanRole === "admin" ? "block" : "none";
    }

    const toggleMyPwdBtn = document.getElementById("btn-toggle-my-pwd-view");
    if (toggleMyPwdBtn) {
      toggleMyPwdBtn.style.display = "inline-block";
    }

    const myPwdText = document.getElementById("my-profile-password");
    if (myPwdText) {
      myPwdText.textContent = "••••••••";
    }

    if (cleanRole === "admin") {
      fetchUserManagementList();
      renderActivityHistoryLogs();
    }

    if (state.catalog && state.catalog.length > 0) {
      renderCatalog(state.catalog);
    }
  }

  function updateRoleUI() {
    applyActiveRole(getActiveRole());
  }
  window.updateRoleUI = updateRoleUI;

  window.switchToEmployeeAccount = function (u) {
    if (!u) return;
    state.viewingEmployeeUser = u;
    applyActiveRole("employee");

    const nameEl = document.getElementById("my-profile-name");
    const userEl = document.getElementById("my-profile-username");
    const pwdEl = document.getElementById("my-profile-password");
    if (nameEl) nameEl.textContent = u.full_name || u.username;
    if (userEl) userEl.textContent = `@${u.username}`;
    if (pwdEl) {
      const userPwd = u.plain_password || (u.username === "employee" ? "newemp789" : u.username === "john" ? "john123" : u.username === "ram" ? "ram123" : u.username === "doggy" ? "doggy123" : "emp123");
      pwdEl.setAttribute("data-pwd", userPwd);
      pwdEl.textContent = "••••••••";
    }

    const userDisplayName = document.getElementById("admin-user-display-name");
    if (userDisplayName) {
      userDisplayName.textContent = `Viewing Account: ${u.full_name || u.username}`;
    }
  };

  function toggleAccountRole() {
    const current = getActiveRole();
    if (current === "admin") {
      applyActiveRole("employee");
    } else {
      state.viewingEmployeeUser = null;
      applyActiveRole("admin");
      if (state.user) {
        updateUserRoleBadge(state.user);
      }
    }

    addActivityLog({
      action: "Account Role Switched",
      details: `Active user role switched to ${getActiveRole() === "admin" ? "Admin" : "Employee"}.`,
      type: "role_switch"
    });
  }

  // ==========================================
  // Auth & Session Management
  // ==========================================
  const DEV_SKIP_LOGIN = false;

  async function checkAuthStatus() {
    const token = window.getAuthToken();
    if (!token) {
      showModal("auth-modal");
      return false;
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/auth/me"));
      if (!res.ok || res.status === 401) {
        window.setAuthToken("");
        showModal("auth-modal");
        return false;
      }

      const data = await res.json();
      if (!data || !data.authenticated || !data.user) {
        window.setAuthToken("");
        showModal("auth-modal");
        return false;
      }

      const userObj = data.user;
      state.user = userObj;
      state.isPrimaryAdmin = (userObj.role === "admin");
      hideModal("auth-modal");
      hideModal("password-reset-modal");
      updateUserRoleBadge(userObj);
      return true;
    } catch (err) {
      console.warn("Auth status check warning:", err);
      window.setAuthToken("");
      showModal("auth-modal");
      return false;
    }
  }

  function updateUserRoleBadge(user) {
    if (!user) return;
    const cleanRole = user.role === "admin" ? "admin" : "employee";
    applyActiveRole(cleanRole);

    const nameEl = document.getElementById("my-profile-name");
    const userEl = document.getElementById("my-profile-username");
    const pwdEl = document.getElementById("my-profile-password");

    if (nameEl) nameEl.textContent = user.full_name || user.username;
    if (userEl) userEl.textContent = `@${user.username}`;
    if (pwdEl) {
      pwdEl.textContent = "••••••••";
      const userPwd = user.plain_password || (user.username === "admin" ? "admin123" : user.username === "employee" ? "newemp789" : user.username === "john" ? "john123" : user.username === "ram" ? "ram123" : user.username === "doggy" ? "doggy123" : "admin123");
      pwdEl.setAttribute("data-pwd", userPwd);
    }
  }

  function showModal(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove("hidden");
      el.style.display = "flex";
    }
  }
  function hideModal(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add("hidden");
      el.style.display = "none";
      if (document.activeElement && typeof document.activeElement.blur === "function") {
        document.activeElement.blur();
      }
      if (id === "auth-modal") {
        window.scrollTo(0, 0);
      }
    }
  }

  window.handleMobileLogin = async function (e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const loginErr = document.getElementById("login-error-text");
    const uInput = document.getElementById("login-username");
    const pInput = document.getElementById("login-password");
    const submitBtn = document.getElementById("btn-login-submit");

    if (loginErr) {
      loginErr.textContent = "";
      loginErr.style.color = "var(--md-sys-color-error, #BA1A1A)";
      loginErr.style.fontWeight = "700";
      loginErr.style.display = "block";
    }

    const u = uInput ? uInput.value.trim() : "";
    const p = pInput ? pInput.value.trim() : "";

    if (!u || !p) {
      if (loginErr) {
        loginErr.textContent = "❌ Incorrect username or password. Access Denied.";
      }
      return false;
    }

    if (submitBtn) submitBtn.disabled = true;

    try {
      const res = await fetch(window.getApiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
      });

      if (!res.ok) {
        let errMsg = "❌ Incorrect username or password. Access Denied.";
        try {
          const errData = await res.json();
          if (errData && (errData.detail || errData.message)) {
            errMsg = `❌ ${errData.detail || errData.message}`;
          }
        } catch (ignore) {}

        if (loginErr) {
          loginErr.textContent = errMsg;
          loginErr.style.color = "var(--md-sys-color-error, #BA1A1A)";
          loginErr.style.fontWeight = "700";
        }
        return false;
      }

      const data = await res.json();
      const token = data.token || data.access_token || "";
      if (!token) {
        if (loginErr) loginErr.textContent = "❌ Incorrect username or password. Access Denied.";
        return false;
      }

      window.setAuthToken(token);
      hideModal("auth-modal");
      hideModal("password-reset-modal");
      await checkAuthStatus();
    } catch (err) {
      if (loginErr) {
        loginErr.textContent = "❌ Network error connecting to server. Please check your connection.";
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
    return false;
  };

  function initAuthEvents() {
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
      loginForm.addEventListener("submit", (e) => window.handleMobileLogin(e));
    }

    const loginBtn = document.getElementById("btn-login-submit");
    if (loginBtn) {
      loginBtn.addEventListener("click", (e) => window.handleMobileLogin(e));
    }

    const toggleLoginPwdBtn = document.getElementById("btn-toggle-login-pwd");
    const loginPwdInput = document.getElementById("login-password");
    if (toggleLoginPwdBtn && loginPwdInput) {
      toggleLoginPwdBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const currentType = loginPwdInput.getAttribute("type");
        if (currentType === "password") {
          loginPwdInput.setAttribute("type", "text");
          toggleLoginPwdBtn.textContent = "🙈";
          toggleLoginPwdBtn.title = "Hide Password";
        } else {
          loginPwdInput.setAttribute("type", "password");
          toggleLoginPwdBtn.textContent = "👁️";
          toggleLoginPwdBtn.title = "View Password";
        }
      });
    }

    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        window.setAuthToken("");
        state.user = null;
        showModal("auth-modal");
      });
    }

    const toggleMyPwdBtn = document.getElementById("btn-toggle-my-pwd-view");
    const myPwdSpan = document.getElementById("my-profile-password");
    
    function toggleMyProfilePasswordText() {
      if (!myPwdSpan) return;
      const pwdVal = myPwdSpan.getAttribute("data-pwd") || "••••••••";
      if (myPwdSpan.textContent === "••••••••") {
        myPwdSpan.textContent = pwdVal;
      } else {
        myPwdSpan.textContent = "••••••••";
      }
    }

    if (toggleMyPwdBtn) {
      toggleMyPwdBtn.addEventListener("click", toggleMyProfilePasswordText);
    }
    if (myPwdSpan) {
      myPwdSpan.style.cursor = "pointer";
      myPwdSpan.title = "Click to reveal/hide password";
      myPwdSpan.addEventListener("click", toggleMyProfilePasswordText);
    }

    const changeMyPwdBtn = document.getElementById("btn-change-my-pwd");
    if (changeMyPwdBtn) {
      changeMyPwdBtn.addEventListener("click", () => {
        if (state.user && state.user.user_id) {
          openEditUserModal({
            user_id: state.user.user_id,
            username: state.user.username,
            full_name: state.user.full_name,
            role: state.user.role
          });
        } else {
          alert("Account session active. Please use password reset form.");
        }
      });
    }
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

  // Fast Client-Side Image Downsampling / Compression Helper (800px max dimension, 0.85 quality)
  function compressImageBeforeUpload(file, maxDimension = 800, quality = 0.85) {
    return new Promise((resolve) => {
      if (!file || !file.type || !file.type.startsWith('image/')) {
        return resolve(file);
      }
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(url);
        let width = img.width;
        let height = img.height;

        if (width <= maxDimension && height <= maxDimension && file.size < 300000) {
          return resolve(file);
        }

        if (width > height) {
          if (width > maxDimension) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          }
        } else {
          if (height > maxDimension) {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob((blob) => {
          if (blob) {
            const compressedFile = new File([blob], file.name || "query.jpg", {
              type: "image/jpeg",
              lastModified: Date.now()
            });
            resolve(compressedFile);
          } else {
            resolve(file);
          }
        }, 'image/jpeg', quality);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(file);
      };
      img.src = url;
    });
  }

  function setQueryFile(file, autoRun = true) {
    state.selectedQueryFile = file;
    const previewContainer = document.getElementById("query-preview-container");
    const previewImg = document.getElementById("query-preview-img");

    // Instantly switch & redirect to Studio tab
    switchTab("tab-studio");

    if (previewImg) {
      if (previewImg.src && previewImg.src.startsWith('blob:')) {
        try { URL.revokeObjectURL(previewImg.src); } catch(e) {}
      }
      previewImg.src = URL.createObjectURL(file);
      previewImg.decoding = 'async';
    }
    if (previewContainer) previewContainer.classList.remove("hidden");

    // Automatically & instantly run AI search upon photo capture
    if (autoRun) {
      runVisualMatch();
    }
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

    // 6. Size Combobox (6-12 dropdown)
    setupCombobox({
      inputId: "catalog-add-materials-input",
      dropdownId: "add-materials-dropdown",
      getSuggestions: () => {
        const deleted = state.customDeletedMaterials || [];
        const defaults = ["Size 6", "Size 7", "Size 8", "Size 9", "Size 10", "Size 11", "Size 12"];
        const fromCatalog = (state.catalog || []).map(d => d.materials).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(m => !deleted.includes(m));
      },
      newItemPrefix: "Add custom size",
      onDeleteItem: (val) => {
        state.customDeletedMaterials = state.customDeletedMaterials || [];
        state.customDeletedMaterials.push(val);
        addActivityLog({
          action: "Size Option Deleted",
          details: `Removed "${val}" from Size selection options.`,
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

    if (submitBtn) {
      submitBtn.disabled = true;
      const span = submitBtn.querySelector("span");
      if (span) span.textContent = "Adding in process...";
    }
    if (loadingRow) loadingRow.style.display = "flex";
    if (statusText) {
      statusText.style.color = "var(--md-sys-color-primary)";
      statusText.style.fontWeight = "700";
      statusText.textContent = "⏳ Adding in process... Please wait";
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
      if (submitBtn) {
        submitBtn.disabled = false;
        const span = submitBtn.querySelector("span");
        if (span) span.textContent = "Add to Catalogue";
      }
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
  function compressAndDownscaleImage(file, maxDimension = 1024, quality = 0.85) {
    return new Promise((resolve) => {
      if (!file || !file.type || !file.type.startsWith("image/")) {
        return resolve(file);
      }
      const img = new Image();
      const objectUrl = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(objectUrl);
        let width = img.width;
        let height = img.height;

        if (width <= maxDimension && height <= maxDimension && file.size <= 300 * 1024) {
          return resolve(file);
        }

        if (width > height) {
          if (width > maxDimension) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          }
        } else {
          if (height > maxDimension) {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            if (blob && blob.size < file.size) {
              const resizedFile = new File([blob], file.name || "query.jpg", {
                type: "image/jpeg",
                lastModified: Date.now()
              });
              resolve(resizedFile);
            } else {
              resolve(file);
            }
          },
          "image/jpeg",
          quality
        );
      };
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(file);
      };
      img.src = objectUrl;
    });
  }

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

    statusText.textContent = "Analyzing Features & Matching Catalog...";
    stepExif.classList.add("done");
    stepU2Net.classList.add("done");
    stepDINO.classList.add("active");
    stepFAISS.classList.add("active");

    try {
      let fileToUpload = state.selectedQueryFile;
      if (fileToUpload && fileToUpload.type && fileToUpload.type.startsWith("image/") && fileToUpload.size > 300 * 1024) {
        try {
          fileToUpload = await compressAndDownscaleImage(fileToUpload, 1024, 0.85);
        } catch (e) {
          console.warn("[ShoeMatch Mobile] Fast image downscale notice:", e);
        }
      }

      const formData = new FormData();
      formData.append("file", fileToUpload);

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
      if (stored !== null) return JSON.parse(stored);
    } catch(e) {}
    const defaults = [
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
    try {
      localStorage.setItem("shoematch_activity_logs", JSON.stringify(defaults));
    } catch(e) {}
    return defaults;
  }

  function refreshActivityHistoryLogs() {
    const listContainer = document.getElementById("admin-activity-history-list");
    if (listContainer) {
      listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-primary); text-align: center; padding: 12px 0; font-weight: 600;">🔄 Refreshing activity logs...</div>`;
    }
    setTimeout(() => {
      renderActivityHistoryLogs();
    }, 250);
  }

  window.clearActivityHistoryLogs = function() {
    try {
      localStorage.setItem("shoematch_activity_logs", JSON.stringify([]));
    } catch(e) {}
    renderActivityHistoryLogs();
  };

  function renderActivityHistoryLogs() {
    const listContainer = document.getElementById("admin-activity-history-list");
    if (!listContainer) return;

    const logs = getActivityLogs();
    if (!logs || logs.length === 0) {
      listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-outline); text-align: center; padding: 12px 0;">No activity history recorded yet.</div>`;
      return;
    }

    listContainer.innerHTML = "";
    logs.forEach(item => {
      const row = document.createElement("div");
      row.style.cssText = "background: var(--md-sys-color-background); border: 1px solid var(--md-sys-color-surface-variant); border-radius: 10px; padding: 10px 12px;";

      let badgeBg = "var(--md-sys-color-primary-container)";
      let badgeFg = "var(--md-sys-color-on-primary-container)";
      let badgeIcon = "📝";

      if (item.type === "ai_search") {
        badgeBg = "var(--md-sys-color-tertiary-container, #E8DEF8)";
        badgeFg = "var(--md-sys-color-on-tertiary-container, #1D192B)";
        badgeIcon = "🔍";
      } else if (item.type === "catalog_add" || item.type === "catalog_edit") {
        badgeBg = "var(--md-sys-color-secondary-container)";
        badgeFg = "var(--md-sys-color-on-secondary-container)";
        badgeIcon = "👟";
      } else if (item.type === "user_action" || item.type === "role_switch") {
        badgeBg = "var(--md-sys-color-surface-variant)";
        badgeFg = "var(--md-sys-color-on-surface-variant)";
        badgeIcon = "👤";
      }

      row.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; flex-wrap: wrap; gap: 4px;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 0.72rem; font-weight: 700; background: ${badgeBg}; color: ${badgeFg}; padding: 2px 8px; border-radius: 6px;">${badgeIcon} ${escapeHtml(item.action)}</span>
          </div>
          <span style="font-size: 0.72rem; font-weight: 600; color: var(--md-sys-color-outline);">${escapeHtml(item.timestamp || "")}</span>
        </div>
        <div style="font-size: 0.82rem; font-weight: 600; color: var(--md-sys-color-on-surface); margin-bottom: 2px;">${escapeHtml(item.details)}</div>
        <div style="font-size: 0.74rem; color: var(--md-sys-color-on-surface-variant);">User: <strong>${escapeHtml(item.user || "Active Account")}</strong></div>
      `;
      listContainer.appendChild(row);
    });
  }

  function addActivityLog(logItem) {
    const logs = getActivityLogs();
    const currentUser = (state.user && (state.user.full_name || state.user.username)) ? (state.user.full_name || `@${state.user.username}`) : "Active Account";
    
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

    renderActivityHistoryLogs();
  }

  function preloadMatchImages(matches) {
    if (!matches || !Array.isArray(matches)) return;

    // Remove any previous preload hints we injected
    document.querySelectorAll('link[data-match-preload]').forEach(el => el.remove());

    // Top 3 results: inject <link rel="preload"> into <head> so the browser
    // fetches them at highest network priority BEFORE the cards are even painted.
    const top3 = matches.slice(0, 3);
    top3.forEach((m, idx) => {
      let rawImg = m.best_matching_image_url || m.image_path || (m.all_angles && m.all_angles[0] ? m.all_angles[0].image_path : '');
      if (!rawImg && m.design_id) rawImg = `/catalog_images/${m.design_id}/photo_1.jpg`;
      if (rawImg) {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = window.getApiUrl(rawImg);
        link.setAttribute('fetchpriority', idx === 0 ? 'high' : 'auto');
        link.setAttribute('data-match-preload', 'true');
        document.head.appendChild(link);
      }
    });

    // Remaining results: standard Image() preload in background
    matches.slice(3).forEach(m => {
      let rawImg = m.best_matching_image_url || m.image_path || (m.all_angles && m.all_angles[0] ? m.all_angles[0].image_path : '');
      if (rawImg) {
        const img = new Image();
        img.src = window.getApiUrl(rawImg);
      }
    });
  }

  function renderMatchResults(data) {
    const alertContainer = document.getElementById("slipper-alert-container");
    const resultsContainer = document.getElementById("match-results-container");

    preloadMatchImages(data.matches);
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

    // Ensure matches are sorted strictly by highest confidence percentage (most relevant first)
    matches.sort((a, b) => {
      const confA = a.confidence_pct !== undefined ? a.confidence_pct : (a.combined_score || a.score || 0);
      const confB = b.confidence_pct !== undefined ? b.confidence_pct : (b.combined_score || b.score || 0);
      return confB - confA;
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
      const rank = idx + 1;
      const confidence = (m.confidence_pct !== undefined ? m.confidence_pct : 0).toFixed(1);
      const designId = m.design_id || `DESIGN_${String(rank).padStart(3, '0')}`;
      
      // Enrich with catalog metadata fallback
      const catalogRef = (state.catalog || []).find(d => d.design_id === designId) || {};
      const designName = m.design_name || m.name || catalogRef.name || designId;
      const category = m.category || catalogRef.category || "Footwear";
      const locationText = m.shelf_location || m.location || catalogRef.shelf_location || "Warehouse Storage";
      const materialsText = m.materials || catalogRef.materials || "Standard";
      const farmaShelfText = (m.farma_shelf || catalogRef.farma_shelf || "").trim();

      // Resolve reference photo URL from match object or angle list
      let rawImg = m.best_matching_image_url || m.image_path || (m.all_angles && m.all_angles[0] ? m.all_angles[0].image_path : '');
      if (!rawImg && catalogRef) {
        rawImg = catalogRef.thumbnail_path || (catalogRef.reference_images && catalogRef.reference_images[0] ? catalogRef.reference_images[0].image_path : '');
      }
      if (!rawImg) {
        rawImg = `/catalog_images/${designId}/photo_1.jpg`;
      }

      const imgPath = window.getApiUrl(rawImg);

      const card = document.createElement("div");
      card.className = `md-card match-card rank-${rank}`;
      if (rank === 1) {
        card.style.border = "2px solid var(--md-sys-color-primary)";
        card.style.boxShadow = "var(--md-elevation-3)";
      }

      card.innerHTML = `
        <div class="match-badge" style="${rank === 1 ? 'background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); font-weight: 800;' : ''}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="${rank === 1 ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span>#${rank} ${rank === 1 ? 'MOST RELEVANT MATCH' : 'MATCH'} • ${confidence}% CONFIDENCE</span>
        </div>
        <div class="card-title" style="margin-top: 8px;">${escapeHtml(designName)}</div>
        <div style="font-size: 0.8rem; color: var(--md-sys-color-outline); margin-bottom: 10px;">SKU: ${escapeHtml(designId)} • Category: ${escapeHtml(category)}</div>
        
        <div style="position: relative; text-align: center; margin-bottom: 12px; border-radius: 12px; overflow: hidden; min-height: 140px; display: flex; align-items: center; justify-content: center;
          ${rank <= 3 ? 'background-color: var(--md-sys-color-background); border: 1px solid var(--md-sys-color-surface-variant); padding: 8px;' : 'background: linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%); background-size:200% 100%; animation: catalogShimmer 1.4s infinite;'}">
          <img src="${imgPath}" alt="${escapeHtml(designName)}"
               loading="${rank <= 3 ? 'eager' : 'lazy'}"
               decoding="async"
               fetchpriority="${rank === 1 ? 'high' : rank <= 3 ? 'auto' : 'low'}"
               style="width: 100%; max-height: 200px; object-fit: contain; border-radius: 8px; transition: opacity 0.15s ease; ${rank <= 3 ? 'opacity:1;' : 'opacity:0;'}"
               onload="this.style.opacity='1'; this.parentElement.style.animation='none'; this.parentElement.style.background='var(--md-sys-color-background)'; this.parentElement.style.border='1px solid var(--md-sys-color-surface-variant)'; this.parentElement.style.padding='8px';"
               onerror="this.onerror=null; this.style.opacity='1'; this.parentElement.style.animation='none'; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23D97706\' stroke-width=\'2\'><rect x=\'3\' y=\'3\' width=\'18\' height=\'18\' rx=\'2\'/><path d=\'M2 17l10 4 10-4\'/><path d=\'M12 3L2 8l10 5 10-5-10-5z\'/></svg>';" />
        </div>
        
        <div style="font-size: 0.82rem; color: var(--md-sys-color-on-surface-variant); margin-bottom: 8px;">
          Size / Material: <strong>${escapeHtml(materialsText)}</strong>
        </div>

        ${farmaShelfText ? `
        <div style="font-size: 0.82rem; color: var(--md-sys-color-secondary); font-weight: 600; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; background-color: var(--md-sys-color-secondary-container); padding: 6px 10px; border-radius: 8px; width: fit-content;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          <span>Farma Shelf: ${escapeHtml(farmaShelfText)}</span>
        </div>
        ` : ''}

        <div class="location-chip">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <span>${escapeHtml(locationText)}</span>
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
      // Phase 1: fetch first 50 designs for instant first paint
      const resFirst = await window.authenticatedFetch(window.getApiUrl("/api/designs?limit=50&page=1"));
      if (!resFirst.ok) return;
      const dataFirst = await resFirst.json();
      const firstBatch = dataFirst.designs || (Array.isArray(dataFirst) ? dataFirst : []);
      state.catalog = firstBatch;
      state.totalDesignsCount = dataFirst.total !== undefined ? dataFirst.total : firstBatch.length;
      renderCatalog(state.catalog);

      // Phase 2: if more designs exist, load the full set silently in background
      if (state.totalDesignsCount > 50) {
        setTimeout(async () => {
          try {
            const resAll = await window.authenticatedFetch(window.getApiUrl("/api/designs?limit=10000"));
            if (!resAll.ok) return;
            const dataAll = await resAll.json();
            state.catalog = dataAll.designs || (Array.isArray(dataAll) ? dataAll : []);
            state.totalDesignsCount = dataAll.total !== undefined ? dataAll.total : state.catalog.length;
            renderCatalog(state.catalog);
          } catch (e) { /* silently ignore background load errors */ }
        }, 300);
      }
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
    if (materialsInput) {
      let rawMat = String(design.materials || "").trim();
      let matchDigit = rawMat.match(/\b(6|7|8|9|10|11|12)\b/);
      if (matchDigit) {
        materialsInput.value = matchDigit[1];
      } else {
        materialsInput.value = (["6","7","8","9","10","11","12"].includes(rawMat)) ? rawMat : "";
      }
      if (window.syncSizeDisplay) {
        window.syncSizeDisplay("catalog-edit-materials-input", "catalog-edit-materials-display");
      }
    }
    if (statusText) statusText.textContent = "";
    if (loadingRow) loadingRow.style.display = "none";

    const deleteBtn = document.getElementById("btn-catalog-edit-delete");
    if (deleteBtn) {
      deleteBtn.style.display = checkUserCanDelete() ? "inline-flex" : "none";
    }

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

    if (!checkUserCanDelete()) {
      alert("Access Restricted: Catalogue delete permission is disabled for your account. Contact Administrator to enable deletion.");
      return;
    }
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
        const defaults = ["Size 6", "Size 7", "Size 8", "Size 9", "Size 10", "Size 11", "Size 12"];
        const fromCatalog = (state.catalog || []).map(d => d.materials).filter(Boolean);
        return Array.from(new Set([...defaults, ...fromCatalog])).filter(m => !deleted.includes(m));
      },
      newItemPrefix: "Use custom size",
      onDeleteItem: (val) => {
        state.customDeletedMaterials = state.customDeletedMaterials || [];
        state.customDeletedMaterials.push(val);
        addActivityLog({
          action: "Size Option Deleted",
          details: `Removed "${val}" from Size selection options.`,
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

    initCustomSizeDropdowns();
  }

  function initCustomSizeDropdowns() {
    setupCustomSizeDropdown("catalog-add-materials-display", "add-size-dropdown", "catalog-add-materials-input", window.updateAddModalLiveSku);
    setupCustomSizeDropdown("catalog-edit-materials-display", "edit-size-dropdown", "catalog-edit-materials-input", window.updateEditModalLiveSku);
  }

  function setupCustomSizeDropdown(displayId, dropdownId, hiddenSelectId, onChangeCallback) {
    const displayEl = document.getElementById(displayId);
    const dropdownEl = document.getElementById(dropdownId);
    const selectEl = document.getElementById(hiddenSelectId);
    if (!displayEl || !dropdownEl || !selectEl) return;

    displayEl.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".farma-shelf-dropdown").forEach(d => {
        if (d !== dropdownEl) d.classList.add("hidden");
      });
      dropdownEl.classList.toggle("hidden");
    });

    dropdownEl.querySelectorAll(".farma-shelf-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const val = item.getAttribute("data-val") || "";
        selectEl.value = val;
        displayEl.value = val ? `Size ${val}` : "-- Select Size (6 to 12) --";
        dropdownEl.classList.add("hidden");
        if (typeof onChangeCallback === "function") onChangeCallback();
      });
    });

    document.addEventListener("click", () => {
      dropdownEl.classList.add("hidden");
    });
  }

  window.syncSizeDisplay = function(hiddenSelectId, displayId) {
    const selectEl = document.getElementById(hiddenSelectId);
    const displayEl = document.getElementById(displayId);
    if (!selectEl || !displayEl) return;
    const val = selectEl.value;
    displayEl.value = val ? `Size ${val}` : "-- Select Size (6 to 12) --";
  };

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

  window.renderTotalDesignLog = function() {
    const badgeEl = document.getElementById("admin-total-designs-badge");
    const countEl = document.getElementById("stat-total-designs-count");
    const catEl = document.getElementById("stat-total-categories-count");
    const shelfEl = document.getElementById("stat-total-shelves-count");
    const summaryEl = document.getElementById("admin-design-log-summary");

    const catalog = state.catalog || [];
    const totalCount = catalog.length;

    const categories = new Set(catalog.map(d => d.category).filter(Boolean));
    const shelves = new Set(catalog.map(d => d.farma_shelf).filter(Boolean));

    if (badgeEl) badgeEl.textContent = `Total Designs: ${totalCount}`;
    if (countEl) countEl.textContent = totalCount;
    if (catEl) catEl.textContent = categories.size;
    if (shelfEl) shelfEl.textContent = shelves.size;

    if (summaryEl) {
      if (totalCount === 0) {
        summaryEl.textContent = "No shoe designs currently registered in catalog.";
      } else {
        const latestDesign = catalog[0];
        const latestName = latestDesign ? (latestDesign.name || latestDesign.design_id) : "N/A";
        summaryEl.innerHTML = `<strong>Catalog Status:</strong> 🟢 Active with <strong>${totalCount}</strong> design${totalCount === 1 ? '' : 's'} across <strong>${categories.size}</strong> categories. Latest entry: <em>${escapeHtml(latestName)}</em>.`;
      }
    }
  };

  function renderCatalog(items) {
    if (window.renderTotalDesignLog) window.renderTotalDesignLog();

    const grid = document.getElementById("catalog-grid");
    if (!grid) return;
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
        <div style="display: flex; flex-direction: column; width: 100%; min-width: 0;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px; width: 100%; margin-bottom: 4px;">
            <div style="font-size: 0.70rem; font-weight: 700; color: var(--md-sys-color-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;" title="${escapeHtml(item.design_id)}">${escapeHtml(item.design_id)}</div>
            <button class="catalog-edit-btn" data-id="${escapeHtml(item.design_id)}" title="Edit Design" style="flex-shrink: 0;">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              <span>Edit</span>
            </button>
          </div>
          <div class="card-title" style="margin: 0; font-size: 0.92rem; font-weight: 700; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%;" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
        </div>

        <div style="position: relative; width: 100%; text-align: center; margin: 6px 0; height: 110px; border-radius: 10px; overflow: hidden; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: catalogShimmer 1.4s infinite;">
          <img src="${imgPath}" loading="lazy" decoding="async" style="width: 100%; height: 110px; object-fit: contain; border-radius: 10px; background-color: transparent; display: block; opacity: 0; transition: opacity 0.3s ease;" onload="this.style.opacity='1'; this.parentElement.style.animation='none'; this.parentElement.style.background='var(--md-sys-color-background)';" onerror="this.onerror=null; this.style.opacity='1'; this.parentElement.style.animation='none'; this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23D97706\' stroke-width=\'2\'><rect x=\'3\' y=\'3\' width=\'18\' height=\'18\' rx=\'2\'/><path d=\'M2 17l10 4 10-4\'/><path d=\'M12 3L2 8l10 5 10-5-10-5z\'/></svg>';" />
        </div>

        <div style="font-size: 0.75rem; color: var(--md-sys-color-on-surface-variant); line-height: 1.35; width: 100%; min-width: 0;">
          <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.category || "Footwear")}</div>
          ${item.farma_shelf ? `<div style="font-weight: 600; color: var(--md-sys-color-primary); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="Farma Shelf: ${escapeHtml(item.farma_shelf)}">Farma Shelf: ${escapeHtml(item.farma_shelf)}</div>` : ""}
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
        if (getActiveRole() === "employee") {
          editBtn.style.display = "none";
        } else {
          editBtn.style.display = "inline-flex";
          editBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            openCatalogEditModal(item.design_id);
          });
        }
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

    if (q) {
      combinedItems.sort((a, b) => {
        const aId = (a.design_id || "").toLowerCase();
        const bId = (b.design_id || "").toLowerCase();
        const aName = (a.name || "").toLowerCase();
        const bName = (b.name || "").toLowerCase();

        const getScore = (id, name) => {
          if (id === q) return 100;
          if (id.startsWith(q)) return 90;
          if (id.includes(q)) return 80;
          if (name.startsWith(q)) return 70;
          if (name.includes(q)) return 60;
          return 10;
        };

        return getScore(bId, bName) - getScore(aId, aName);
      });
    }

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
    fetchUserManagementList();
  }

  // ==========================================
  // User Management (Admin Only)
  // ==========================================
  async function fetchUserManagementList() {
    const listContainer = document.getElementById("admin-users-list");
    if (!listContainer) return;

    if (getActiveRole() !== "admin") {
      const card = document.getElementById("admin-user-management-card");
      if (card) card.style.display = "none";
      return;
    } else {
      const card = document.getElementById("admin-user-management-card");
      if (card) card.style.display = "block";
    }

    try {
      const res = await window.authenticatedFetch(window.getApiUrl("/api/admin/users"));
      if (!res.ok) {
        listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-error); text-align: center; padding: 8px 0;">Could not load user accounts.</div>`;
        return;
      }

      const data = await res.json();
      const users = data.users || [];
      state.allUsers = users;
      updateEmployeeSwitchDropdown(users);

      if (users.length === 0) {
        listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-outline); text-align: center; padding: 8px 0;">No user accounts found.</div>`;
        return;
      }

      listContainer.innerHTML = "";
      users.forEach(u => {
        const item = document.createElement("div");
        item.style.cssText = "display: flex; align-items: center; justify-content: space-between; background: var(--md-sys-color-background); padding: 10px 12px; border-radius: 10px; border: 1px solid var(--md-sys-color-surface-variant); flex-wrap: wrap; gap: 8px;";

        const isAllowed = Boolean(u.can_delete === 1 || u.can_delete === true || u.can_delete === "1");
        const btnBg = isAllowed ? "#2e7d32" : "#d32f2f";
        const btnColor = "#ffffff";
        const btnText = isAllowed ? "✅ Delete Allowed" : "🚫 Allow Delete";
        const btnBorder = isAllowed ? "#1b5e20" : "#b71c1c";
        const btnShadow = isAllowed ? "rgba(46, 125, 50, 0.35)" : "rgba(211, 47, 47, 0.35)";

        const roleBadgeBg = u.role === "admin" ? "var(--md-sys-color-primary-container)" : "var(--md-sys-color-secondary-container)";
        const roleBadgeFg = u.role === "admin" ? "var(--md-sys-color-on-primary-container)" : "var(--md-sys-color-on-secondary-container)";
        const roleLabel = u.role === "admin" ? "Admin" : "Employee";
        const plainPwd = u.plain_password || u.password_plain || (u.username === "admin" ? "admin123" : u.username === "employee" ? "newemp789" : u.username === "john" ? "john123" : u.username === "ram" ? "ram123" : u.username === "doggy" ? "doggy123" : (u.password || "admin123"));

        item.innerHTML = `
          <div style="flex: 1; min-width: 160px;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
              <span style="font-size: 0.88rem; font-weight: 700; color: var(--md-sys-color-on-surface);">${escapeHtml(u.full_name || u.username)}</span>
              <span style="font-size: 0.68rem; font-weight: 700; background: ${roleBadgeBg}; color: ${roleBadgeFg}; padding: 2px 8px; border-radius: 6px;">${roleLabel}</span>
            </div>
            <div style="font-size: 0.76rem; color: var(--md-sys-color-on-surface-variant); display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span>@${escapeHtml(u.username)}</span>
              <span style="display: inline-flex; align-items: center; gap: 4px; background: var(--md-sys-color-surface-variant); padding: 2px 6px; border-radius: 4px;">
                <span>Password:</span>
                <span class="user-pwd-text" data-pwd="${escapeHtml(plainPwd)}" style="font-family: monospace; font-weight: 700;">••••••••</span>
                <button class="btn-toggle-pwd-view" style="background: none; border: none; cursor: pointer; padding: 0 2px; color: var(--md-sys-color-primary);" title="Reveal/Hide Password">👁️</button>
              </span>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            ${u.role === "employee" ? `
            <button class="md-btn btn-view-user-acc" data-id="${u.user_id}" style="padding: 4px 8px; font-size: 0.72rem; min-height: 30px; background-color: var(--md-sys-color-primary-container); color: var(--md-sys-color-on-primary-container); width: auto;" title="View app as this employee">
              <span>👁️ View Account</span>
            </button>
            <button class="md-btn btn-toggle-can-delete" data-id="${u.user_id}" data-can-delete="${isAllowed ? 1 : 0}" style="padding: 5px 10px; font-size: 0.76rem; font-weight: 700; min-height: 32px; background-color: ${btnBg}; color: ${btnColor}; border: 1px solid ${btnBorder}; box-shadow: 0 2px 6px ${btnShadow}; border-radius: 6px; width: auto; cursor: pointer;" title="Toggle Catalog Delete Permission for this employee">
              <span>${btnText}</span>
            </button>
            ` : ''}
            <button class="md-btn btn-edit-user-pwd" data-id="${u.user_id}" data-user="${escapeHtml(u.username)}" data-name="${escapeHtml(u.full_name)}" data-role="${u.role}" style="padding: 4px 8px; font-size: 0.72rem; min-height: 30px; background-color: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); width: auto;" title="Change Password / Account Details">
              <span>🔑 Change Password</span>
            </button>
            ${u.username !== "admin" ? `
            <button class="md-btn btn-delete-user" data-id="${u.user_id}" data-user="${escapeHtml(u.username)}" style="padding: 4px 8px; font-size: 0.72rem; min-height: 30px; background-color: var(--md-sys-color-error-container); color: var(--md-sys-color-on-error-container); width: auto;" title="Delete User Account">
              <span>🗑️ Delete</span>
            </button>
            ` : ''}
          </div>
        `;

        const viewAccBtn = item.querySelector(".btn-view-user-acc");
        if (viewAccBtn) {
          viewAccBtn.addEventListener("click", () => {
            window.switchToEmployeeAccount(u);
          });
        }

        const toggleDeleteBtn = item.querySelector(".btn-toggle-can-delete");
        if (toggleDeleteBtn) {
          toggleDeleteBtn.addEventListener("click", async (e) => {
            if (e) {
              e.preventDefault();
              e.stopPropagation();
            }
            const currentAllowed = Boolean(u.can_delete === 1 || u.can_delete === true || u.can_delete === "1");
            const newCanDelete = currentAllowed ? 0 : 1;
            const nextAllowed = (newCanDelete === 1);

            // ⚡ Immediate Bright Optimistic UI Update (0ms Delay)
            u.can_delete = newCanDelete;
            const spanEl = toggleDeleteBtn.querySelector("span");
            if (spanEl) spanEl.textContent = nextAllowed ? "✅ Delete Allowed" : "🚫 Allow Delete";
            toggleDeleteBtn.style.backgroundColor = nextAllowed ? "#2e7d32" : "#d32f2f";
            toggleDeleteBtn.style.color = "#ffffff";
            toggleDeleteBtn.style.borderColor = nextAllowed ? "#1b5e20" : "#b71c1c";
            toggleDeleteBtn.style.boxShadow = `0 2px 6px ${nextAllowed ? "rgba(46, 125, 50, 0.35)" : "rgba(211, 47, 47, 0.35)"}`;
            toggleDeleteBtn.setAttribute("data-can-delete", nextAllowed ? "1" : "0");

            try {
              const res = await window.authenticatedFetch(window.getApiUrl(`/api/admin/users/${u.user_id}`), {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ can_delete: newCanDelete })
              });
              if (res.ok) {
                if (state.user && state.user.user_id === u.user_id) {
                  state.user.can_delete = newCanDelete;
                }
                if (state.viewingEmployeeUser && state.viewingEmployeeUser.user_id === u.user_id) {
                  state.viewingEmployeeUser.can_delete = newCanDelete;
                }
                if (window.showMobileToast) {
                  window.showMobileToast(`Delete permission ${newCanDelete ? 'ENABLED' : 'DISABLED'} for @${u.username}`, "info");
                }
                updateRoleUI();
              } else {
                u.can_delete = currentAllowed ? 1 : 0;
                fetchUserManagementList();
                alert("Failed to update delete permission for user.");
              }
            } catch (err) {
              u.can_delete = currentAllowed ? 1 : 0;
              fetchUserManagementList();
              alert("Error updating user permission: " + err.message);
            }
          });
        }

        const pwdToggleBtn = item.querySelector(".btn-toggle-pwd-view");
        const pwdTextSpan = item.querySelector(".user-pwd-text");
        if (pwdTextSpan) {
          pwdTextSpan.style.cursor = "pointer";
          pwdTextSpan.title = "Click to reveal/hide password";
          const toggleRowPwd = (e) => {
            if (e) {
              e.preventDefault();
              e.stopPropagation();
            }
            const pwdVal = pwdTextSpan.getAttribute("data-pwd") || "admin123";
            if (pwdTextSpan.textContent === "••••••••") {
              pwdTextSpan.textContent = pwdVal;
            } else {
              pwdTextSpan.textContent = "••••••••";
            }
          };
          pwdTextSpan.addEventListener("click", toggleRowPwd);
          if (pwdToggleBtn) {
            pwdToggleBtn.addEventListener("click", toggleRowPwd);
          }
        }

        const editBtn = item.querySelector(".btn-edit-user-pwd");
        if (editBtn) {
          editBtn.addEventListener("click", () => {
            openEditUserModal({
              user_id: u.user_id,
              username: u.username,
              full_name: u.full_name,
              role: u.role,
              plain_password: u.plain_password || plainPwd
            });
          });
        }

        const delBtn = item.querySelector(".btn-delete-user");
        if (delBtn) {
          delBtn.addEventListener("click", () => {
            deleteUserAccount(u.user_id, u.username);
          });
        }

        listContainer.appendChild(item);
      });

    } catch (err) {
      listContainer.innerHTML = `<div style="font-size: 0.82rem; color: var(--md-sys-color-error); text-align: center; padding: 8px 0;">Error fetching user accounts.</div>`;
    }
  }

  window.openCreateUserModal = function() {
    const modal = document.getElementById("user-modal");
    const title = document.getElementById("user-modal-title");
    const editIdInput = document.getElementById("user-modal-edit-id");
    const fullnameInput = document.getElementById("user-modal-fullname-input");
    const usernameInput = document.getElementById("user-modal-username-input");
    const pwdInput = document.getElementById("user-modal-password-input");
    const roleSelect = document.getElementById("user-modal-role-select");
    const statusText = document.getElementById("user-modal-status-text");

    if (title) title.textContent = "Create New User";
    if (editIdInput) editIdInput.value = "";
    if (fullnameInput) fullnameInput.value = "";
    if (usernameInput) {
      usernameInput.value = "";
      usernameInput.disabled = false;
    }
    if (pwdInput) pwdInput.value = "";
    if (roleSelect) roleSelect.value = "employee";
    if (statusText) statusText.textContent = "";

    if (modal) modal.classList.remove("hidden");
  };

  function openEditUserModal(user) {
    const modal = document.getElementById("user-modal");
    const title = document.getElementById("user-modal-title");
    const editIdInput = document.getElementById("user-modal-edit-id");
    const fullnameInput = document.getElementById("user-modal-fullname-input");
    const usernameInput = document.getElementById("user-modal-username-input");
    const pwdInput = document.getElementById("user-modal-password-input");
    const roleSelect = document.getElementById("user-modal-role-select");
    const statusText = document.getElementById("user-modal-status-text");

    if (title) title.textContent = `Edit Account @${user.username}`;
    if (editIdInput) editIdInput.value = user.user_id;
    if (fullnameInput) fullnameInput.value = user.full_name || "";
    if (usernameInput) {
      usernameInput.value = user.username || "";
      usernameInput.disabled = true;
    }
    if (pwdInput) {
      pwdInput.value = user.plain_password || (user.username === "admin" ? "admin123" : user.username === "employee" ? "emp123" : "");
    }
    if (roleSelect) roleSelect.value = user.role || "employee";
    if (statusText) statusText.textContent = "";

    if (modal) modal.classList.remove("hidden");
  }

  window.closeUserModal = function() {
    const modal = document.getElementById("user-modal");
    if (modal) modal.classList.add("hidden");
  };

  async function submitUserForm() {
    const editIdInput = document.getElementById("user-modal-edit-id");
    const fullnameInput = document.getElementById("user-modal-fullname-input");
    const usernameInput = document.getElementById("user-modal-username-input");
    const pwdInput = document.getElementById("user-modal-password-input");
    const roleSelect = document.getElementById("user-modal-role-select");
    const statusText = document.getElementById("user-modal-status-text");
    const submitBtn = document.getElementById("btn-submit-user-form");

    const userId = editIdInput ? editIdInput.value : "";
    const fullName = fullnameInput ? fullnameInput.value.trim() : "";
    const username = usernameInput ? usernameInput.value.trim() : "";
    const password = pwdInput ? pwdInput.value.trim() : "";
    const role = roleSelect ? roleSelect.value : "employee";

    if (!userId && (!username || !password || !fullName)) {
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-error)";
        statusText.textContent = "Please fill in all required user fields.";
      }
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (statusText) {
      statusText.style.color = "var(--md-sys-color-on-surface-variant)";
      statusText.textContent = "Saving user account...";
    }

    try {
      let res;
      if (userId) {
        // Edit existing user
        res = await window.authenticatedFetch(window.getApiUrl(`/api/admin/users/${userId}`), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: fullName,
            role: role,
            password: password || undefined
          })
        });
      } else {
        // Create new user
        res = await window.authenticatedFetch(window.getApiUrl("/api/admin/users"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: username,
            password: password,
            full_name: fullName,
            role: role
          })
        });
      }

      const data = await res.json();
      if (!res.ok || data.success === false) {
        if (statusText) {
          statusText.style.color = "var(--md-sys-color-error)";
          statusText.textContent = data.detail || data.message || "Failed to save user account.";
        }
        return;
      }

      if (statusText) {
        statusText.style.color = "var(--md-sys-color-secondary)";
        statusText.textContent = "User account saved successfully!";
      }

      addActivityLog({
        action: userId ? "User Account Updated" : "New User Created",
        details: `${userId ? 'Updated' : 'Created'} @${username} (${role === 'admin' ? 'Admin' : 'Employee'})`,
        type: "user_management"
      });

      if (state.user && (String(state.user.user_id) === String(userId) || state.user.username === username)) {
        if (fullName) state.user.full_name = fullName;
        if (role) state.user.role = role;
        if (password) state.user.plain_password = password;
        updateUserRoleBadge(state.user);
      }

      fetchUserManagementList();
      closeUserModal();

    } catch (err) {
      if (statusText) {
        statusText.style.color = "var(--md-sys-color-error)";
        statusText.textContent = "Network error saving user account.";
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  async function deleteUserAccount(userId, username) {
    if (!confirm(`Are you sure you want to delete user account '@${username}'?`)) {
      return;
    }

    try {
      let res = await window.authenticatedFetch(window.getApiUrl(`/api/admin/users/${userId}`), {
        method: "DELETE"
      });

      if (res.status === 405) {
        res = await window.authenticatedFetch(window.getApiUrl(`/api/admin/users/${userId}/delete`), {
          method: "POST"
        });
      }

      const data = await res.json();

      if (!res.ok || data.success === false) {
        alert(data.detail || data.message || "Could not delete user account.");
        fetchUserManagementList();
        return;
      }

      addActivityLog({
        action: "User Account Deleted",
        details: `Deleted user account @${username} (ID #${userId})`,
        type: "user_management"
      });

      fetchUserManagementList();
    } catch (err) {
      alert("Network error deleting user account.");
      fetchUserManagementList();
    }
  }

  function initUserManagementEvents() {
    const openBtn = document.getElementById("btn-open-create-user");
    if (openBtn) {
      openBtn.addEventListener("click", () => {
        openCreateUserModal();
      });
    }

    const submitBtn = document.getElementById("btn-submit-user-form");
    if (submitBtn) {
      submitBtn.addEventListener("click", () => {
        submitUserForm();
      });
    }

    const togglePwdBtn = document.getElementById("btn-toggle-user-modal-password");
    if (togglePwdBtn) {
      togglePwdBtn.addEventListener("click", () => {
        const pwdInput = document.getElementById("user-modal-password-input");
        if (pwdInput) {
          pwdInput.type = pwdInput.type === "password" ? "text" : "password";
        }
      });
    }

    const refreshLogsBtn = document.getElementById("btn-refresh-activity-logs");
    if (refreshLogsBtn) {
      refreshLogsBtn.addEventListener("click", (e) => {
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        refreshActivityHistoryLogs();
      });
    }

    const clearLogsBtn = document.getElementById("btn-clear-activity-logs");
    if (clearLogsBtn) {
      clearLogsBtn.addEventListener("click", (e) => {
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        if (confirm("Are you sure you want to clear all activity history logs?")) {
          window.clearActivityHistoryLogs();
        }
      });
    }

    const openSwitchModalBtn = document.getElementById("btn-open-switch-employee-modal");
    if (openSwitchModalBtn) {
      openSwitchModalBtn.addEventListener("click", () => {
        window.openSwitchEmployeeModal();
      });
    }

    const returnAdminBtn = document.getElementById("btn-return-to-admin");
    if (returnAdminBtn) {
      returnAdminBtn.addEventListener("click", () => {
        state.viewingEmployeeUser = null;
        applyActiveRole("admin");
        if (state.user) {
          updateUserRoleBadge(state.user);
        }
      });
    }
  }

  function updateEmployeeSwitchDropdown(users) {
    const selectSwitch = document.getElementById("select-switch-employee-view");
    if (!selectSwitch) return;

    selectSwitch.innerHTML = `<option value="">-- Switch to Employee View --</option>`;
    const employees = (users || []).filter(u => u.role === "employee");
    employees.forEach(emp => {
      const opt = document.createElement("option");
      opt.value = emp.user_id;
      opt.textContent = `${emp.full_name || emp.username} (@${emp.username})`;
      selectSwitch.appendChild(opt);
    });
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
    initUserManagementEvents();

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
