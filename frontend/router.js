/**
 * ShoeMatch AI — Frontend Router & Navigation Controller
 * Centralized Route Registry & Application Navigation Helper
 */

(function (window) {
  'use strict';

  const API_BASE = window.location.origin;

  /**
   * Application Route Registry
   */
  const ROUTES = {
    // Page Routes
    HOME: '/',
    LANDING: '/index.html',
    APP: '/app.html',
    WEB_APP: '/app',
    MOBILE: '/mobile',
    MOBILE_INDEX: '/mobile/index.html',

    // API Endpoints
    API_HEALTH: '/api/health',
    API_MATCH: '/api/match',
    API_DESIGNS: '/api/designs',
    API_FARMA_SHELVES: '/api/designs/farma-shelves',
    API_LOGS: '/api/logs',
    API_LOGIN: '/api/login',
    API_ME: '/api/me'
  };

  /**
   * Client-Side Router Helper
   */
  class AppRouter {
    constructor() {
      this.routes = ROUTES;
    }

    /**
     * Get absolute API URL for a given path
     */
    getApiUrl(endpoint) {
      if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
        return endpoint;
      }
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      return `${API_BASE}${cleanEndpoint}`;
    }

    /**
     * Navigate to a target application page
     */
    navigateTo(routeKey) {
      const target = ROUTES[routeKey] || routeKey;
      window.location.href = this.getApiUrl(target);
    }

    /**
     * Launch Mobile Application
     */
    openMobileApp() {
      window.location.href = this.getApiUrl(ROUTES.MOBILE);
    }

    /**
     * Launch Desktop Web Studio
     */
    openWebApp() {
      window.location.href = this.getApiUrl(ROUTES.APP);
    }

    /**
     * Fetch System Health Metrics
     */
    async fetchHealthMetrics() {
      try {
        const res = await fetch(this.getApiUrl(ROUTES.API_HEALTH));
        if (!res.ok) return null;
        return await res.json();
      } catch (err) {
        console.warn('Router health fetch warning:', err);
        return null;
      }
    }
  }

  // Export to global window
  window.ShoeMatchRouter = new AppRouter();
  window.ROUTES = ROUTES;
})(window);
