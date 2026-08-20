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

window.getImageUrl = function(path) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const base = window.getApiBaseUrl();
  const cleanPath = path.startsWith("/") ? path : "/" + path;
  return base ? base + cleanPath : cleanPath;
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
    }
  };

  // ==========================================
  // Initialization & Stats
  // ==========================================
  async function init() {
    restoreSidebarState();
    setupEventListeners();

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

    // Update Navigation UI
    elements.navButtons.forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });

    elements.tabPanes.forEach(pane => {
      pane.classList.toggle("active", pane.id === tabId);
    });

    // Update Topbar
    const config = tabTitles[tabId] || tabTitles["match-tab"];
    elements.pageTitle.textContent = config.title;
    elements.pageDescription.textContent = config.desc;

    // Refresh Tab-specific data
    if (tabId === "catalog-tab") fetchCatalog();
    if (tabId === "logs-tab") fetchLogs();
  }

  // ==========================================
  // Event Listeners Setup
  // ==========================================
  function setupEventListeners() {
    // Navigation
    elements.navButtons.forEach(btn => {
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

    // Catalog Actions
    if (elements.catalogSearchInput) elements.catalogSearchInput.addEventListener("input", filterCatalogCards);
    if (elements.catalogCategoryFilter) elements.catalogCategoryFilter.addEventListener("change", filterCatalogCards);
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
          <div class="angles-strip" onclick="event.stopPropagation();">
            <span style="font-size: 0.7rem; color: var(--text-muted);">Angles:</span>
            ${m.all_angles.map(a => `
              <img src="${getImageUrl(a.image_path)}" 
                   class="angle-thumb ${a.image_path === m.best_matching_image_url ? 'active' : ''}" 
                   title="Angle: ${a.angle}" 
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
          <img src="${getImageUrl(m.best_matching_image_url)}" alt="${m.design_name}">
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
            <div class="color-palette-strip" style="display: flex; gap: 6px; align-items: center; margin: 6px 0;" onclick="event.stopPropagation();">
              <span style="font-size: 0.72rem; color: var(--text-muted); font-weight: 500;">Colors:</span>
              ${m.dominant_colors.map(c => `
                <span style="width: 14px; height: 14px; border-radius: 50%; background: ${c.hex}; border: 1px solid rgba(0,0,0,0.15); display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.1);" title="${c.hex} (${c.percentage}%)"></span>
              `).join("")}
            </div>
          ` : ''}
          
          <div class="match-action-hint" style="margin-top: 6px;">
            <button type="button" class="btn-inspect-quick-action" style="background: none; border: none; color: var(--brand-primary); font-size: 0.78rem; font-weight: 700; cursor: pointer; padding: 0; display: inline-flex; align-items: center; gap: 4px;" onclick="event.stopPropagation(); openShoeInspectionModal('${m.design_id}', ${m.confidence_pct});">
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
        if (e.target && (e.target.closest(".match-feedback-row") || e.target.closest(".angles-strip") || e.target.closest(".color-palette-strip"))) {
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
      const res = await fetch("/api/feedback", {
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

      // Highlight active thumb
      const parent = thumbEl.parentElement;
      if (parent) {
        parent.querySelectorAll(".angle-thumb").forEach(t => t.classList.remove("active"));
        thumbEl.classList.add("active");
      }
    }
  };

  // ==========================================
  // Catalog Explorer
  // ==========================================
  async function fetchCatalog() {
    try {
      const res = await fetch(getApiUrl("/api/designs"));
      if (res.ok) {
        const data = await res.json();
        state.catalog = data.designs || [];
        renderCatalogGrid(state.catalog);
        if (elements.navCatalogCount) elements.navCatalogCount.textContent = state.catalog.length;
      }
    } catch (err) {
      console.error("Failed to fetch catalog:", err);
    }
  }

  function renderCatalogGrid(designs) {
    elements.catalogGrid.innerHTML = "";

    if (designs.length === 0) {
      elements.catalogGrid.innerHTML = `
        <div class="results-empty" style="grid-column: 1 / -1;">
          <h4>No Designs in Catalog</h4>
          <p>Click "Add New Design" to upload reference photos.</p>
        </div>
      `;
      return;
    }

    designs.forEach(d => {
      const card = document.createElement("div");
      card.className = "catalog-card";
      card.onclick = () => openShoeInspectionModal(d.design_id, null);

      const shelf = d.shelf_location || "Warehouse A - Rack 03 - Shelf B-02";

      card.innerHTML = `
        <div class="catalog-card-img">
          <img src="${getImageUrl(d.thumbnail_path || '/static/placeholder.jpg')}" alt="${d.name}" loading="lazy">
          <span class="catalog-card-pill">${d.design_id}</span>
          <span class="catalog-card-count">${d.image_count || 1} angles</span>
        </div>
        <div class="catalog-card-body">
          <h4 class="catalog-card-title">${d.name}</h4>
          <span class="catalog-card-cat">${d.category} &bull; ${d.created_by}</span>
          
          <div class="match-card-shelf-badge" style="margin: 6px 0;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <span><strong>Shelf:</strong> ${shelf}</span>
          </div>

          <p class="catalog-card-desc">${d.description || "Manufactured catalog specification."}</p>
        </div>
      `;

      elements.catalogGrid.appendChild(card);
    });
  }

  function filterCatalogCards() {
    const query = elements.catalogSearchInput.value.toLowerCase().trim();
    const category = elements.catalogCategoryFilter.value;

    const filtered = state.catalog.filter(d => {
      const matchesQuery = d.name.toLowerCase().includes(query) ||
                           d.design_id.toLowerCase().includes(query) ||
                           (d.shelf_location && d.shelf_location.toLowerCase().includes(query)) ||
                           (d.description && d.description.toLowerCase().includes(query));
      const matchesCategory = category === "ALL" || d.category === category;
      return matchesQuery && matchesCategory;
    });

    renderCatalogGrid(filtered);
  }

  // ==========================================================================
  // Full Shoe Inspection & Warehouse Shelf Location Modal
  // ==========================================================================
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
            <div class="preview-match-meta">
              <div style="display: flex; align-items: center; gap: 8px;">
                <h4 style="color: var(--brand-primary); font-weight: 700;">${rankTitle}</h4>
                <span class="match-level-pill ${normalizedMatch.match_color}">${normalizedMatch.match_level_label}</span>
              </div>
              <span>Query Match Confidence: <strong>${normalizedMatch.confidence_pct}%</strong>${normalizedMatch.cosine_similarity !== undefined ? ` &bull; Visual Cosine: ${(normalizedMatch.cosine_similarity * 100).toFixed(1)}%` : ''}</span>
            </div>
            <div class="preview-score-badge ${normalizedMatch.match_color}">
              ${normalizedMatch.confidence_pct}%
            </div>
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
              <img id="preview-active-image" src="${firstImage}" alt="${design.name}">
              <span class="viewer-angle-pill" id="preview-angle-pill">Angle: ${firstAngle}</span>
              ${hasQueryPhoto ? `
                <button class="viewer-toggle-btn" id="btn-toggle-split" onclick="toggleComparisonSplit('${firstImage}', '${queryPreviewSrc}')">
                  ⚡ Side-by-Side Compare
                </button>
              ` : ''}
            </div>

            <!-- Multi-Angle Thumbnails Strip -->
            <div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; text-transform: uppercase;">
                Multi-Angle Reference Photos (${referenceImages.length} angle${referenceImages.length === 1 ? '' : 's'} available)
              </div>
              <div class="preview-thumbnails-strip" id="preview-thumb-strip">
                ${referenceImages.map((img, idx) => `
                  <button class="preview-thumb-btn ${idx === 0 ? 'active' : ''}" 
                          onclick="selectPreviewAngle('${getImageUrl(img.image_path)}', '${img.angle}', this)"
                          title="View ${img.angle} angle">
                    <img src="${getImageUrl(img.image_path)}" alt="${img.angle}">
                    <span class="preview-thumb-tag">${img.angle}</span>
                  </button>
                `).join("")}
              </div>
            </div>
          </div>

          <!-- Right Column: Warehouse Location & Specifications -->
          <div class="preview-info-col">
            ${matchBannerHtml}

            <!-- WAREHOUSE SHELF LOCATION CARD -->
            <div class="warehouse-locator-card">
              <div class="locator-card-header">
                <div class="locator-header-title">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  <span>Company Shelf Location</span>
                </div>
                <span class="locator-badge">${design.production_status || "Sample Room Archive"}</span>
              </div>

              <div class="shelf-coordinate-display">
                <div class="shelf-icon-box">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/></svg>
                </div>
                <div>
                  <div class="shelf-main-location" id="display-shelf-text">${design.shelf_location || "Warehouse A - Rack 03 - Shelf B-02"}</div>
                  <div class="shelf-sub-desc">Physical shelf coordinate in factory inventory system</div>
                </div>
              </div>

              <div class="shelf-actions-bar">
                <button class="btn-shelf-edit" onclick="toggleShelfEditForm('${design.design_id}')">
                  ✏️ Edit Shelf Location
                </button>
                <button class="btn-shelf-edit" onclick="printSampleTicket('${design.design_id}', '${design.name}', '${design.shelf_location}')">
                  🖨️ Print Shelf Tag
                </button>
              </div>

              <!-- Inline Shelf Edit Form (Hidden by default) -->
              <div class="shelf-edit-form" id="shelf-edit-form" style="display: none;">
                <label style="font-size: 0.75rem; color: #93c5fd;">Update Company Warehouse Shelf Coordinates:</label>
                <input type="text" id="input-shelf-location" value="${design.shelf_location || 'Warehouse A - Rack 03 - Shelf B-02'}" placeholder="e.g. Building B - Rack C-04 - Shelf 2">
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
                <span>Manufacturing & Technical Specs</span>
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
                  <span class="spec-val">${design.materials || "Full Grain Leather / Rubber Sole"}</span>
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
                  <span class="spec-val">${design.created_at || "Recent"}</span>
                </div>
              </div>

              <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-color);">
                <span class="spec-label">Design Description:</span>
                <p style="font-size: 0.85rem; color: var(--text-primary); margin-top: 4px; line-height: 1.4;">
                  ${design.description || "Manufactured factory model registered in production catalog."}
                </p>
              </div>
            </div>

            <!-- Modal Footer Actions -->
            <div class="preview-modal-footer">
              <button class="btn btn-danger btn-sm" onclick="deleteDesign('${design.design_id}')">
                Delete Design
              </button>
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('detail-modal').style.display = 'none'">
                Close Preview
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
        <img id="preview-active-image" src="${imgPath}" alt="${angle}">
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
        <img id="preview-active-image" src="${catalogImgSrc}" alt="Catalog Reference">
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
            <img src="${queryImgSrc}" alt="Query Target">
            <span class="split-label">Target Query Photo</span>
          </div>
          <div class="split-box">
            <img src="${catalogImgSrc}" alt="Catalog Match">
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
  // Audit Logs
  // ==========================================
  async function fetchLogs() {
    try {
      const res = await fetch(getApiUrl("/api/logs?limit=50"));
      if (res.ok) {
        const data = await res.json();
        state.logs = data.logs || [];
        renderLogsTable(state.logs);
      }
    } catch (err) {
      console.error("Failed to fetch logs:", err);
    }
  }

  function renderLogsTable(logs) {
    elements.logsTbody.innerHTML = "";

    if (logs.length === 0) {
      elements.logsTbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No queries logged yet. Run a match in the Studio to generate logs.
          </td>
        </tr>
      `;
      return;
    }

    logs.forEach(log => {
      const tr = document.createElement("tr");

      const level = (log.confidence_pct >= 85) ? "HIGH" : (log.confidence_pct >= 70) ? "MODERATE" : "LOW";
      const color = (log.confidence_pct >= 85) ? "green" : (log.confidence_pct >= 70) ? "yellow" : "red";
      const isNone = (log.detected_category === "none");
      const isSlipper = (log.detected_category === "slipper");
      const catBadge = isNone ? '<span style="color: #f87171; font-weight: 600; font-size: 0.8rem;">🚫 None</span>' :
                       (isSlipper ? '<span style="color: #60a5fa; font-weight: 600; font-size: 0.8rem;">🩴 Slipper</span>' : '<span style="color: #34d399; font-weight: 600; font-size: 0.8rem;">👟 Shoe</span>');

      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">${log.created_at}</td>
        <td>
          <img src="${getImageUrl(log.query_image_path)}" class="log-thumb" alt="Query" onerror="this.src='/static/placeholder.jpg'">
        </td>
        <td>${catBadge}</td>
        <td>
          <strong>${log.top_match_name || "No Match"}</strong>
          <br><span style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--text-muted);">${log.top_match_id || "--"}</span>
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700; font-size: 0.95rem;">
          <span style="color: var(--color-${color});">${log.confidence_pct}%</span>
          <br><span class="score-level-badge ${color}" style="font-size: 0.68rem; padding: 1px 6px;">${level}</span>
        </td>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${log.latency_ms} ms</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="reMatchFromLog('${log.query_image_path}')">Re-match</button>
        </td>
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

  // Start Application
  init();
});
