/**
 * ShoeMatch AI — Frontend Application Logic (Vanilla JavaScript)
 */

document.addEventListener("DOMContentLoaded", () => {
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
      const res = await fetch("/api/stats");
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

    // File Drop & Selection for Query Studio (Click anywhere in the box to upload)
    if (elements.queryDropzone) {
      elements.queryDropzone.addEventListener("click", (e) => {
        if (!state.selectedQueryFile || e.target.closest("#btn-change-image")) {
          elements.queryFileInput.click();
        }
      });
    }
    if (elements.btnBrowseFile) elements.btnBrowseFile.addEventListener("click", (e) => {
      e.stopPropagation();
      elements.queryFileInput.click();
    });
    if (elements.btnChangeImage) elements.btnChangeImage.addEventListener("click", (e) => {
      e.stopPropagation();
      elements.queryFileInput.click();
    });
    if (elements.queryFileInput) elements.queryFileInput.addEventListener("change", handleQueryFileSelect);

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
      e.stopPropagation();
      resetQueryStudio();
    });
    if (elements.btnRunMatch) elements.btnRunMatch.addEventListener("click", executeVisualMatch);

    // Catalog Actions
    if (elements.catalogSearchInput) elements.catalogSearchInput.addEventListener("input", filterCatalogCards);
    if (elements.catalogCategoryFilter) elements.catalogCategoryFilter.addEventListener("change", filterCatalogCards);
    if (elements.btnRefreshCatalog) elements.btnRefreshCatalog.addEventListener("click", fetchCatalog);
    if (elements.btnRefreshLogs) elements.btnRefreshLogs.addEventListener("click", fetchLogs);

    // Modal Events
    if (elements.btnOpenAddModal) elements.btnOpenAddModal.addEventListener("click", openAddModal);
    if (elements.btnCloseAddModal) elements.btnCloseAddModal.addEventListener("click", closeAddModal);
    if (elements.btnCancelAdd) elements.btnCancelAdd.addEventListener("click", closeAddModal);
    if (elements.btnCloseDetailModal) elements.btnCloseDetailModal.addEventListener("click", () => elements.detailModal.style.display = "none");

    // Camera Capture Events
    if (elements.btnOpenCamera) {
      elements.btnOpenCamera.addEventListener("click", (e) => {
        e.stopPropagation();
        openCameraModal();
      });
    }
    if (elements.btnRecaptureCamera) {
      elements.btnRecaptureCamera.addEventListener("click", (e) => {
        e.stopPropagation();
        openCameraModal();
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

  function setQueryFile(file) {
    if (!file.type.startsWith("image/")) {
      showToast("Please select a valid image file (JPEG, PNG, WEBP)", "error");
      return;
    }

    state.selectedQueryFile = file;
    const objectUrl = URL.createObjectURL(file);

    // Show Preview
    elements.dropPrompt.style.display = "none";
    elements.queryPreviewContainer.style.display = "block";
    elements.queryPreviewImg.src = objectUrl;
    elements.btnClearQuery.style.display = "inline-block";
    elements.btnRunMatch.disabled = false;

    // Reset results to prompt matching
    elements.resultsEmpty.style.display = "block";
    elements.resultsLoading.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsMetaText.textContent = "Ready to search catalog";
    elements.latencyBadge.style.display = "none";
  }

  function resetQueryStudio() {
    state.selectedQueryFile = null;
    elements.queryFileInput.value = "";
    elements.dropPrompt.style.display = "block";
    elements.queryPreviewContainer.style.display = "none";
    elements.queryPreviewImg.src = "";
    elements.btnClearQuery.style.display = "none";
    elements.btnRunMatch.disabled = true;

    elements.resultsEmpty.style.display = "block";
    elements.resultsLoading.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsMetaText.textContent = "Awaiting query image";
    elements.latencyBadge.style.display = "none";
    if (elements.detectedCategoryBadge) elements.detectedCategoryBadge.style.display = "none";
  }

  async function executeVisualMatch() {
    if (!state.selectedQueryFile) return;

    // UI Loading State
    elements.resultsEmpty.style.display = "none";
    elements.matchesList.style.display = "none";
    elements.resultsLoading.style.display = "block";
    elements.btnRunMatch.disabled = true;
    elements.resultsMetaText.textContent = "Searching catalog...";
    if (elements.detectedCategoryBadge) elements.detectedCategoryBadge.style.display = "none";

    const formData = new FormData();
    formData.append("file", state.selectedQueryFile);
    formData.append("top_k", "3");

    try {
      const response = await fetch("/api/match", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Matching failed");
      }

      const data = await response.json();
      renderMatchResults(data);
      fetchStats(); // Update query count in sidebar
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
      elements.resultsEmpty.querySelector("h4").textContent = "🚫 No Shoe or Slipper Detected";
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

      const rankLabels = ["#1 Best Match", "#2 Second Best", "#3 Third Best"];
      const rankLabel = rankLabels[m.rank - 1] || `#${m.rank} Match`;

      // Build angle thumbnails
      let angleThumbsHtml = "";
      if (m.all_angles && m.all_angles.length > 0) {
        angleThumbsHtml = `
          <div class="angles-strip">
            <span style="font-size: 0.7rem; color: var(--text-muted);">Angles:</span>
            ${m.all_angles.map(a => `
              <img src="${a.image_path}" 
                   class="angle-thumb ${a.image_path === m.best_matching_image_url ? 'active' : ''}" 
                   title="Angle: ${a.angle}" 
                   onclick="event.stopPropagation(); swapMatchImage(this, '${m.design_id}')">
            `).join("")}
          </div>
        `;
      }

      const shelfLocation = m.shelf_location || "Warehouse A - Rack 03 - Shelf B-02";

      card.innerHTML = `
        <div class="match-img-box" id="img-box-${m.design_id}">
          <img src="${m.best_matching_image_url}" alt="${m.design_name}">
          <span class="match-angle-tag">${m.best_matching_angle}</span>
        </div>

        <div class="match-details">
          <div class="match-rank-badge">
            <span>${rankLabel}</span>
          </div>
          <h4 class="match-title">${m.design_name}</h4>
          <span class="match-sku">SKU: ${m.design_id} &bull; ${m.category}</span>
          
          <div class="match-card-shelf-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <span><strong>Shelf:</strong> ${shelfLocation}</span>
          </div>

          <p class="match-desc">${m.description || "Factory specification model."}</p>
          ${angleThumbsHtml}
          
          <div class="match-action-hint">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span>Click to open full shoe preview & shelf location</span>
          </div>
        </div>

        <div class="match-score-block">
          <div class="score-pct ${m.match_color}">${m.confidence_pct}%</div>
          <span class="score-level-badge ${m.match_color}">${m.match_level_label}</span>
          <div class="score-bar-track">
            <div class="score-bar-fill ${m.match_color}" style="width: ${Math.min(100, m.confidence_pct)}%;"></div>
          </div>
        </div>
      `;

      card.onclick = () => openShoeInspectionModal(m.design_id, m);

      elements.matchesList.appendChild(card);
    });
  }

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
      const res = await fetch("/api/designs");
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
          <img src="${d.thumbnail_path || '/static/placeholder.jpg'}" alt="${d.name}" loading="lazy">
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
  window.openShoeInspectionModal = async function(designId, matchData) {
    try {
      const res = await fetch(`/api/designs/${designId}`);
      if (!res.ok) throw new Error("Could not load design details");
      const design = await res.json();

      const skuBadge = document.getElementById("detail-sku-badge");
      const titleEl = document.getElementById("detail-title");
      if (skuBadge) skuBadge.textContent = `SKU: ${design.design_id} • ${design.category}`;
      if (titleEl) titleEl.textContent = `${design.name}`;

      const referenceImages = design.reference_images || [];
      const firstImage = referenceImages.length > 0 ? referenceImages[0].image_path : (design.thumbnail_path || '/static/placeholder.jpg');
      const firstAngle = referenceImages.length > 0 ? referenceImages[0].angle : 'side';

      // Match Banner HTML (if opened from match results)
      let matchBannerHtml = "";
      if (matchData) {
        matchBannerHtml = `
          <div class="preview-match-banner">
            <div class="preview-match-meta">
              <h4 style="color: var(--brand-primary); font-weight: 700;">#${matchData.rank || 1} Ranked Match Result</h4>
              <span>Similarity Confidence: <strong>${matchData.confidence_pct}%</strong> (${matchData.match_level_label})</span>
            </div>
            <div class="preview-score-badge ${matchData.match_color || 'green'}">
              ${matchData.confidence_pct}%
            </div>
          </div>
        `;
      }

      // Query photo split-screen comparison button (if query image exists)
      const hasQueryPhoto = Boolean(state.queryFile);
      const queryPreviewSrc = elements.previewImg ? elements.previewImg.src : null;

      elements.detailModalBody.innerHTML = `
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
                Multi-Angle Reference Photos (${referenceImages.length} angles available)
              </div>
              <div class="preview-thumbnails-strip" id="preview-thumb-strip">
                ${referenceImages.map((img, idx) => `
                  <button class="preview-thumb-btn ${idx === 0 ? 'active' : ''}" 
                          onclick="selectPreviewAngle('${img.image_path}', '${img.angle}', this)">
                    <img src="${img.image_path}" alt="${img.angle}">
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

      elements.detailModal.style.display = "flex";
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Switch active photo in preview modal
  window.selectPreviewAngle = function(imgPath, angle, btnEl) {
    const stage = document.getElementById("preview-stage-box");
    if (stage) {
      stage.innerHTML = `
        <img id="preview-active-image" src="${imgPath}" alt="${angle}">
        <span class="viewer-angle-pill" id="preview-angle-pill">Angle: ${angle}</span>
        ${state.queryFile ? `
          <button class="viewer-toggle-btn" id="btn-toggle-split" onclick="toggleComparisonSplit('${imgPath}', '${elements.previewImg ? elements.previewImg.src : ''}')">
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

      const res = await fetch(`/api/designs/${designId}/location`, {
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
      const res = await fetch(`/api/designs/${designId}`, { method: "DELETE" });
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
      const res = await fetch("/api/designs", {
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
      const res = await fetch("/api/logs?limit=50");
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
          <img src="${log.query_image_path}" class="log-thumb" alt="Query" onerror="this.src='/static/placeholder.jpg'">
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
  // Live Camera Capture
  // ==========================================
  async function openCameraModal() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast("Camera access is not supported by your browser.", "error");
      return;
    }

    if (elements.cameraModal) elements.cameraModal.style.display = "flex";
    if (elements.cameraLoadingNotice) elements.cameraLoadingNotice.style.display = "block";

    await startCameraStream();
  }

  async function startCameraStream() {
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach(track => track.stop());
      state.cameraStream = null;
    }

    try {
      const constraints = {
        video: {
          facingMode: state.cameraFacingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      state.cameraStream = stream;
      if (elements.cameraVideo) {
        elements.cameraVideo.srcObject = stream;
        await elements.cameraVideo.play();
      }
      if (elements.cameraLoadingNotice) elements.cameraLoadingNotice.style.display = "none";

      // Show switch camera button if multiple cameras exist
      if (navigator.mediaDevices.enumerateDevices && elements.btnSwitchCamera) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === "videoinput");
        if (videoDevices.length > 1) {
          elements.btnSwitchCamera.style.display = "inline-flex";
        }
      }
    } catch (err) {
      console.error("Camera access error:", err);
      showToast("Camera permission denied or camera not available.", "error");
      closeCameraModal();
    }
  }

  function closeCameraModal() {
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach(track => track.stop());
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
    if (!elements.cameraVideo || !state.cameraStream) return;

    const video = elements.cameraVideo;
    const canvas = elements.cameraCanvas || document.createElement("canvas");
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;

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
      showToast("Photo captured from live camera!", "success");
      // Automatically execute visual match
      setTimeout(() => executeVisualMatch(), 300);
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
