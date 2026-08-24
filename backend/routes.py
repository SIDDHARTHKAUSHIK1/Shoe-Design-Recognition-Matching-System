"""
ShoeMatch AI — Backend Route Registry & API Architecture
Centralized Route Mapping & Endpoint Specifications
"""

from typing import Dict, List, Any

# Centralized API Route Directory
SYSTEM_ROUTES: Dict[str, Dict[str, Any]] = {
    # Public & UI Page Routes
    "LANDING_PAGE": {
        "path": "/",
        "method": "GET",
        "handler": "serve_landing",
        "description": "Serves official ShoeMatch AI Product Landing Page interface."
    },
    "DESKTOP_WEB_APP": {
        "path": "/app",
        "method": "GET",
        "handler": "serve_app",
        "description": "Serves main desktop web studio interface."
    },
    "MOBILE_PWA_APP": {
        "path": "/mobile",
        "method": "GET",
        "handler": "serve_mobile",
        "description": "Serves Material 3 mobile application interface."
    },

    # Core System Health & Telemetry
    "HEALTH_CHECK": {
        "path": "/api/health",
        "method": "GET",
        "handler": "get_health_status",
        "description": "Returns system health, total catalogue designs count, and vector index size."
    },

    # Visual Matching Engine Endpoints
    "VISUAL_MATCH": {
        "path": "/api/match",
        "method": "POST",
        "handler": "match_shoe_image",
        "description": "Runs DINOv2 feature extraction & FAISS similarity search on uploaded shoe image."
    },

    # Catalogue & Inventory Endpoints
    "LIST_DESIGNS": {
        "path": "/api/designs",
        "method": "GET",
        "handler": "list_catalog_designs",
        "description": "Fetches paginated catalog designs with optional category filtering."
    },
    "GET_DESIGN_BY_ID": {
        "path": "/api/designs/{design_id}",
        "method": "GET",
        "handler": "get_catalog_design_details",
        "description": "Fetches complete reference photos, Farma Shelf, and metadata for a specific SKU."
    },
    "MOBILE_EDIT_DESIGN": {
        "path": "/api/designs/{design_id}/mobile-edit",
        "method": "PUT",
        "handler": "update_design_mobile",
        "description": "Updates design name, category, Farma Shelf, warehouse location, materials, and season."
    },
    "DELETE_DESIGN": {
        "path": "/api/designs/{design_id}",
        "method": "DELETE",
        "handler": "delete_catalog_design",
        "description": "Fast 15ms instant deletion of design record and image folder."
    },
    "GET_FARMA_SHELVES": {
        "path": "/api/designs/farma-shelves",
        "method": "GET",
        "handler": "list_farma_shelves",
        "description": "Fetches unique Farma Shelves and count of associated catalog designs."
    },

    # Audit History & Logs
    "GET_AUDIT_LOGS": {
        "path": "/api/logs",
        "method": "GET",
        "handler": "get_system_audit_logs",
        "description": "Fetches AI visual search attempts and catalogue modification logs."
    },

    # Authentication Endpoints
    "AUTH_LOGIN": {
        "path": "/api/login",
        "method": "POST",
        "handler": "authenticate_user",
        "description": "Authenticates user credentials and issues JWT Bearer token."
    },
    "AUTH_ME": {
        "path": "/api/me",
        "method": "GET",
        "handler": "get_current_user_profile",
        "description": "Returns active authenticated user profile details."
    }
}


def get_route_summary() -> List[Dict[str, str]]:
    """Returns a clean list of all registered API endpoints."""
    return [
        {
            "name": name,
            "path": route["path"],
            "method": route["method"],
            "description": route["description"]
        }
        for name, route in SYSTEM_ROUTES.items()
    ]
