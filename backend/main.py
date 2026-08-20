"""
FastAPI Application Backend for Shoe Design Recognition & Matching System.
"""
import os
import io
import csv
import time
import shutil
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Query, Depends
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import (
    STORAGE_DIR,
    UPLOADS_DIR,
    CATALOG_IMAGES_DIR,
    FRONTEND_DIR,
    HOST,
    PORT,
    DEBUG
)
from backend import database as db
from backend import auth
from backend import bulk_import
from backend.engine import EmbeddingEngine
from backend.classifier import ZeroShotCategoryClassifier
from backend.vector_store import VectorStore
from backend.matcher import ShoeMatcher
from backend.ingestion import ingest_single_design, ingest_catalog_from_dataset
from evaluate import run_evaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# Application lifespan for singleton initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and initialize vector store on server startup."""
    logger.info("Starting Shoe Design Recognition & Matching System...")
    db.init_db()
    
    # Load vision models, classifier and vector store in memory
    _ = EmbeddingEngine.get_instance()
    _ = ZeroShotCategoryClassifier.get_instance()
    _ = VectorStore.get_instance()
    
    # Ingest catalog if not already populated
    if db.get_catalog_stats()["total_designs"] == 0:
        logger.info("Initializing catalog from dataset...")
        ingest_catalog_from_dataset()
        
    logger.info("System startup complete. Ready to serve inference queries.")
    yield
    logger.info("Shutting down Shoe Design Recognition System...")


app = FastAPI(
    title="Shoe Design Recognition & Matching API",
    description="Production visual similarity search and catalog matching for shoe manufacturing.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local or internal network clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global matcher instance
matcher = ShoeMatcher()


# Static file mounts
app.mount("/catalog_images", StaticFiles(directory=str(CATALOG_IMAGES_DIR)), name="catalog_images")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


# ==========================================
# REST API Endpoints
# ==========================================

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    stats = db.get_catalog_stats()
    return JSONResponse(content={
        "status": "healthy",
        "service": "ShoeMatch AI",
        "total_designs": stats.get("total_designs", 0),
        "total_vectors": VectorStore.get_instance().total_vectors
    })


@app.post("/api/match")
async def match_shoe_design(
    request: Request,
    file: UploadFile = File(...),
    top_k: int = Form(3)
):
    """
    Match an uploaded shoe image against the catalog.
    Returns the top 3 ranked designs with accuracy percentages, confidence levels,
    and side-by-side reference angle images.
    """
    if file.content_type and not file.content_type.startswith("image/"):
        # Check filename extension if content_type is generic/binary
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            raise HTTPException(status_code=400, detail="Uploaded file must be a valid image (JPEG, PNG, WEBP).")

    # Read image contents
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty image file received.")

    # Save query image to persistent uploads directory
    timestamp = int(time.time() * 1000)
    safe_filename = f"query_{timestamp}_{file.filename}"
    save_path = UPLOADS_DIR / safe_filename
    
    with open(save_path, "wb") as f:
        f.write(contents)

    rel_url = f"/uploads/{safe_filename}"

    # Execute matching
    result = matcher.match_image(
        query_image_input=contents,
        query_image_save_path=rel_url,
        top_k=top_k
    )

    # Attach current logged in user_id to logged query if authenticated
    try:
        user = await get_current_user(request)
        if user and user.get("user_id"):
            with db.get_db_connection() as conn:
                conn.execute(
                    "UPDATE query_logs SET user_id = ? WHERE id = (SELECT MAX(id) FROM query_logs)",
                    (user["user_id"],)
                )
                conn.commit()
    except Exception as e:
        logger.warning(f"Could not bind user_id to query_log: {e}")

    return JSONResponse(content=result)


@app.post("/api/designs")
async def create_design(
    design_id: str = Form(...),
    name: str = Form(...),
    category: str = Form("Sneaker"),
    description: str = Form(""),
    created_by: str = Form("Design Team"),
    shelf_location: str = Form("Warehouse A - Rack 03 - Shelf B-02"),
    materials: str = Form("Full Grain Leather / Rubber Sole"),
    season: str = Form("Collection 2026"),
    production_status: str = Form("Active Production Sample"),
    files: List[UploadFile] = File(...),
    angles: Optional[str] = Form(None)  # Comma-separated or inferred
):
    """
    Incrementally add a new shoe design to the catalog with multiple angle photos.
    Uses FAISS incremental add() without rebuilding the entire index.
    """
    if not design_id or not name:
        raise HTTPException(status_code=400, detail="design_id and name are required.")

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one reference image is required.")

    # Parse angles if provided
    angle_list = [a.strip() for a in angles.split(",")] if angles else []

    image_payloads = []
    for idx, uploaded_file in enumerate(files):
        content = await uploaded_file.read()
        if len(content) > 0:
            assigned_angle = angle_list[idx] if idx < len(angle_list) else None
            image_payloads.append({
                "filename": uploaded_file.filename,
                "content": content,
                "angle": assigned_angle
            })

    if not image_payloads:
        raise HTTPException(status_code=400, detail="No valid images uploaded.")

    # Perform incremental ingestion
    ingest_result = ingest_single_design(
        design_id=design_id.strip(),
        name=name.strip(),
        category=category.strip(),
        description=description.strip(),
        created_by=created_by.strip(),
        shelf_location=shelf_location.strip(),
        materials=materials.strip(),
        season=season.strip(),
        production_status=production_status.strip(),
        image_files=image_payloads
    )

    return JSONResponse(content=ingest_result)


@app.put("/api/designs/{design_id}/location")
async def update_shoe_shelf_location(
    design_id: str,
    shelf_location: str = Form(...),
    production_status: Optional[str] = Form(None)
):
    """
    Update the physical warehouse shelf location and status of a shoe design.
    """
    design = db.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found.")
        
    db.update_design_location(design_id, shelf_location, production_status)
    return JSONResponse(content={
        "success": True, 
        "design_id": design_id, 
        "shelf_location": shelf_location,
        "production_status": production_status
    })


@app.get("/api/designs")
async def list_designs(
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "newest",
    page: int = 1,
    limit: int = 100
):
    """Retrieve catalog shoe designs with optional filter, search, sort, and pagination."""
    designs = db.get_all_designs()
    
    # Filter by category
    if category and category.strip():
        c_lower = category.strip().lower()
        designs = [d for d in designs if (d.get("category") or "").lower() == c_lower]

    # Filter by status (active/archived)
    if status and status.strip():
        st = status.strip().lower()
        if st == "active":
            designs = [d for d in designs if d.get("is_active", 1) == 1 and d.get("is_archived", 0) == 0]
        elif st == "archived":
            designs = [d for d in designs if d.get("is_archived", 0) == 1]
        elif st == "deactivated":
            designs = [d for d in designs if d.get("is_active", 1) == 0]

    # Filter by search string
    if search and search.strip():
        q = search.strip().lower()
        designs = [
            d for d in designs
            if q in (d.get("name") or "").lower() or
               q in (d.get("design_id") or "").lower() or
               q in (d.get("materials") or "").lower() or
               q in (d.get("shelf_location") or "").lower()
        ]

    # Sort
    if sort == "oldest":
        designs = sorted(designs, key=lambda x: x.get("created_at") or "")
    elif sort == "name_asc":
        designs = sorted(designs, key=lambda x: (x.get("name") or "").lower())
    elif sort == "name_desc":
        designs = sorted(designs, key=lambda x: (x.get("name") or "").lower(), reverse=True)
    else:
        designs = sorted(designs, key=lambda x: x.get("created_at") or "", reverse=True)

    total = len(designs)
    start_idx = max(0, (page - 1) * limit)
    paginated_designs = designs[start_idx : start_idx + limit]

    return JSONResponse(content={"total": total, "designs": paginated_designs, "page": page, "limit": limit})


@app.put("/api/designs/{design_id}")
async def update_design(design_id: str, payload: dict, request: Request):
    """Update design attributes (name, category, materials, shelf_location, etc.)."""
    _ = await require_authenticated_user(request)
    design = db.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found.")

    success = db.update_design_metadata(design_id, **payload)
    if not success:
        raise HTTPException(status_code=400, detail="No metadata attributes updated.")

    return JSONResponse(content={"success": True, "design_id": design_id, "message": "Design metadata updated successfully."})


@app.put("/api/admin/designs/{design_id}/status")
async def toggle_admin_design_status(design_id: str, payload: dict, request: Request):
    """Activate, deactivate, or archive a design (Admin only). Excluded from candidate pool when inactive/archived."""
    _ = await require_admin_user(request)
    design = db.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found.")

    is_active = payload.get("is_active")
    is_archived = payload.get("is_archived")

    success = db.update_design_status(design_id, is_active=is_active, is_archived=is_archived)
    return JSONResponse(content={"success": True, "design_id": design_id, "is_active": is_active, "is_archived": is_archived})


@app.get("/api/designs/{design_id}")
async def get_design_details(design_id: str):
    """Retrieve a single design along with all its multi-angle reference photos."""
    design = db.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found.")
    return JSONResponse(content=design)


@app.delete("/api/designs/{design_id}")
async def delete_catalog_design(design_id: str):
    """Delete a design and refresh the vector store."""
    design = db.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found.")

    # Remove storage folder
    design_dir = CATALOG_IMAGES_DIR / design_id
    if design_dir.exists():
        shutil.rmtree(design_dir, ignore_errors=True)

    # Delete from DB
    db.delete_design(design_id)

    # Rebuild shoe-only index from remaining DB reference images
    vs = VectorStore.get_instance()
    vs.reset()
    all_refs = db.get_all_shoe_reference_images()


    
    if all_refs:
        engine = EmbeddingEngine.get_instance()
        images = []
        for r in all_refs:
            p = CATALOG_IMAGES_DIR / r["design_id"] / Path(r["image_path"]).name
            if p.exists():
                images.append(p)
                
        if images:
            embs = engine.get_batch_embeddings(images)
            assigned_ids = vs.add_vectors(embs)
            
            # Update FAISS IDs in DB
            with db.get_db_connection() as conn:
                for r, new_fid in zip(all_refs, assigned_ids):
                    conn.execute("UPDATE reference_images SET faiss_id = ? WHERE id = ?;", (new_fid, r["id"]))
                conn.commit()

    return JSONResponse(content={"success": True, "message": f"Design {design_id} deleted."})



@app.get("/api/logs")
async def get_logs(request: Request, limit: int = 50, user_id: Optional[int] = None):
    """Retrieve recent query audit logs."""
    current_user = await get_current_user(request)
    filter_user_id = user_id
    if current_user and current_user.get("role") == "employee":
        filter_user_id = current_user.get("user_id")
        
    logs = db.get_query_logs(limit=limit, user_id=filter_user_id)
    return JSONResponse(content={"total": len(logs), "logs": logs})


@app.get("/api/stats")
async def get_stats():
    """Retrieve catalog and inference statistics."""
    stats = db.get_catalog_stats()
    return JSONResponse(content=stats)


from pydantic import BaseModel

class FeedbackPayload(BaseModel):
    query_id: Optional[int] = None
    user_verdict: str  # 'correct', 'wrong_match', 'not_in_catalog', 'wrong_category'
    correct_design_id: Optional[str] = None
    notes: Optional[str] = ""

@app.post("/api/feedback")
async def submit_match_feedback(payload: FeedbackPayload):
    """
    Record operator/user feedback on a search query.
    Verdict: 'correct', 'wrong_match', 'not_in_catalog', 'wrong_category'
    """
    res = db.record_feedback(
        query_id=payload.query_id,
        user_verdict=payload.user_verdict,
        correct_design_id=payload.correct_design_id,
        notes=payload.notes or ""
    )
    return JSONResponse(content={"success": True, "feedback": res})


@app.get("/api/feedback")
async def list_feedback_logs(limit: int = 100):
    """Retrieve recent match feedback logs."""
    logs = db.get_feedback_logs(limit=limit)
    return JSONResponse(content={"total": len(logs), "feedback_logs": logs})


@app.post("/api/evaluate")
async def trigger_evaluation():
    """Run catalog Leave-One-Out benchmark and return performance metrics."""
    report = run_evaluation()
    return JSONResponse(content=report)


# ==========================================================================
# Auth & Role Foundation Dependencies and Endpoints (Phase 1)
# ==========================================================================

async def get_current_user(request: Request) -> Optional[dict]:
    """Extract authenticated user payload from Bearer header or cookie."""
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif "session_token" in request.cookies:
        token = request.cookies.get("session_token")
        
    if not token:
        return None
        
    payload = auth.verify_token(token)
    if not payload:
        return None
        
    user = auth.get_user_by_id(payload["user_id"])
    if not user or user.get("is_active") == 0:
        return None
        
    return user


async def require_authenticated_user(request: Request) -> dict:
    """Dependency ensuring caller is authenticated."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin_user(request: Request) -> dict:
    """Dependency ensuring caller is an Admin."""
    user = await require_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


@app.post("/api/auth/login")
async def login_user(payload: dict):
    """Authenticate user and return JWT token."""
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
        
    user = auth.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = auth.create_token(user["user_id"], user["username"], user["role"])
    
    response = JSONResponse(content={
        "token": token,
        "user": user,
        "message": "Login successful"
    })
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)
    return response


@app.post("/api/auth/logout")
async def logout_user():
    """Logout current session."""
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="session_token")
    return response


@app.get("/api/auth/me")
async def get_my_profile(request: Request):
    """Get profile of current logged in user."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse(content={"authenticated": False, "user": None})
    return JSONResponse(content={"authenticated": True, "user": user})


@app.post("/api/auth/change-password")
async def change_password(payload: dict, request: Request):
    """Change current user's password."""
    user = await require_authenticated_user(request)
    old_password = payload.get("old_password", "").strip()
    new_password = payload.get("new_password", "").strip()

    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="old_password and new_password are required.")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    success = auth.change_user_password(user["user_id"], old_password, new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    return JSONResponse(content={"success": True, "message": "Password changed successfully. Forced change flag reset."})


# ==========================================================================
# Admin Management & User CRUD Endpoints (Phase 3)
# ==========================================================================

@app.get("/api/admin/users")
async def list_admin_users(request: Request):
    """Retrieve list of registered users (Admin only)."""
    _ = await require_admin_user(request)
    users = auth.list_users()
    return JSONResponse(content={"total": len(users), "users": users})


@app.post("/api/admin/users")
async def create_admin_user(payload: dict, request: Request):
    """Create a new user account (Admin only)."""
    _ = await require_admin_user(request)
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    role = payload.get("role", "employee").strip()
    full_name = payload.get("full_name", "").strip()

    if not username or not password or not full_name:
        raise HTTPException(status_code=400, detail="Username, password, and full_name are required.")

    if role not in ("employee", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'employee' or 'admin'.")

    user_id = auth.create_user(username, password, role, full_name)
    if not user_id:
        raise HTTPException(status_code=400, detail=f"Username '{username}' already exists.")

    return JSONResponse(content={"success": True, "user_id": user_id, "message": f"User '{username}' created successfully."})


@app.put("/api/admin/users/{user_id}")
async def update_admin_user(user_id: int, payload: dict, request: Request):
    """Update user role, active status, or reset password (Admin only)."""
    _ = await require_admin_user(request)
    role = payload.get("role")
    full_name = payload.get("full_name")
    is_active = payload.get("is_active")
    password = payload.get("password")

    success = auth.update_user(user_id, role=role, full_name=full_name, is_active=is_active, password=password)
    if not success:
        raise HTTPException(status_code=400, detail="Could not update user or no fields changed.")

    return JSONResponse(content={"success": True, "message": f"User ID {user_id} updated successfully."})


@app.get("/api/admin/stats")
async def get_admin_system_stats(request: Request):
    """Retrieve system analytics and match distribution stats (Admin only)."""
    _ = await require_admin_user(request)
    stats = db.get_catalog_stats()
    users = auth.list_users()
    logs = db.get_query_logs(limit=500)

    # Compute confidence distribution
    high_count = sum(1 for l in logs if (l.get("confidence_pct") or 0) >= 85)
    mod_count = sum(1 for l in logs if 70 <= (l.get("confidence_pct") or 0) < 85)
    low_count = sum(1 for l in logs if (l.get("confidence_pct") or 0) < 70)

    return JSONResponse(content={
        "total_users": len(users),
        "total_designs": stats.get("total_designs", 0),
        "total_queries": len(logs),
        "confidence_distribution": {
            "high": high_count,
            "moderate": mod_count,
            "low": low_count
        }
    })


# ==============================================================================
# BULK DATA MANAGEMENT ENDPOINTS (CSV/EXCEL & PAIRED ZIP)
# ==============================================================================

@app.post("/api/admin/bulk-import/preview")
async def bulk_import_preview_endpoint(
    file: UploadFile = File(...),
    images_zip: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_admin_user)
):
    """
    Parse spreadsheet (.csv, .xlsx) and optional ZIP image archive.
    Validates all rows and returns preview breakdown before any database writes occur.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Spreadsheet file (.csv or .xlsx) is required")

    spreadsheet_bytes = await file.read()
    if not spreadsheet_bytes:
        raise HTTPException(status_code=400, detail="Empty spreadsheet file uploaded")

    try:
        rows = bulk_import.parse_spreadsheet_bytes(spreadsheet_bytes, file.filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse spreadsheet: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in spreadsheet")

    # Extract images from paired ZIP if provided
    zip_images = {}
    if images_zip and images_zip.filename and images_zip.filename.lower().endswith(".zip"):
        zip_bytes = await images_zip.read()
        if zip_bytes:
            try:
                zip_images = bulk_import.extract_zip_images(zip_bytes)
            except Exception as ze:
                raise HTTPException(status_code=400, detail=f"Failed to parse ZIP archive: {ze}")

    summary, validated_rows = bulk_import.validate_bulk_rows(rows, zip_images)
    
    return JSONResponse(content={
        "summary": summary,
        "rows": validated_rows,
        "filename": file.filename,
        "has_zip_images": bool(zip_images),
        "total_zip_designs_found": len(zip_images)
    })


@app.post("/api/admin/bulk-import/execute")
async def bulk_import_execute_endpoint(
    payload: dict,
    current_user: dict = Depends(require_admin_user)
):
    """
    Execute batch ingestion for validated rows calling single-design ingestion path in loop.
    Accepts duplicate_handling strategy ('skip' or 'overwrite').
    """
    validated_rows = payload.get("rows", [])
    duplicate_handling = payload.get("duplicate_handling", "skip")
    
    if not validated_rows:
        raise HTTPException(status_code=400, detail="No rows provided for execution")

    # If ZIP images passed in payload or session, fetch
    zip_images = {}
    
    result = bulk_import.execute_bulk_import_batch(
        validated_rows=validated_rows,
        zip_images=zip_images,
        duplicate_handling=duplicate_handling
    )

    return JSONResponse(content=result)


@app.post("/api/admin/bulk-import/export-failed")
async def export_failed_rows_csv_endpoint(
    payload: dict,
    current_user: dict = Depends(require_admin_user)
):
    """Generate and return a downloadable CSV of failed rows with error reasons."""
    details = payload.get("details", [])
    failed_items = [d for d in details if d.get("status") == "failed"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Row Number", "Design ID", "Name", "Status", "Failure Reason"])
    
    for item in failed_items:
        writer.writerow([
            item.get("row_num", ""),
            item.get("design_id", ""),
            item.get("name", ""),
            item.get("status", ""),
            item.get("reason", "")
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=failed_import_rows.csv"}
    )


# ==============================================================================
# LOCATION HIERARCHY & SLOT MANAGEMENT ENDPOINTS
# ==============================================================================

@app.get("/api/locations/hierarchy")
async def get_locations_hierarchy_endpoint(request: Request):
    """Fetch complete location hierarchy tree (Shoe Matches -> Shelves -> Drawers -> Slots)."""
    hierarchy = db.get_location_hierarchy()
    return JSONResponse(content={"hierarchy": hierarchy})


@app.get("/api/locations/slots")
async def get_flat_slots_endpoint(
    request: Request,
    search: str = Query("", description="Search term for slot, drawer, shelf, or design"),
    zone_id: Optional[int] = Query(None, description="Filter by Shoe Match / Zone ID"),
    status: str = Query("", description="Filter by occupancy status: occupied or vacant")
):
    """Fetch flat list of physical slots with full location path and design assignment."""
    slots = db.get_all_slots_flat(search=search, zone_id=zone_id, status_filter=status)
    return JSONResponse(content={"slots": slots, "total": len(slots)})


@app.post("/api/locations/shoe-matches")
async def create_shoe_match_endpoint(payload: dict, current_user: dict = Depends(require_admin_user)):
    """Create a new top-level Shoe Match / Zone."""
    name = payload.get("name", "").strip()
    desc = payload.get("description", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Shoe Match / Zone name is required")
    try:
        res = db.create_shoe_match(name, desc)
        return JSONResponse(content={"message": "Shoe Match created", "data": res}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/locations/shoe-matches/{sm_id}")
async def update_shoe_match_endpoint(sm_id: int, payload: dict, current_user: dict = Depends(require_admin_user)):
    """Update Shoe Match name/description."""
    name = payload.get("name", "").strip()
    desc = payload.get("description", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    ok = db.update_shoe_match(sm_id, name, desc)
    if not ok:
        raise HTTPException(status_code=404, detail="Shoe Match not found")
    return JSONResponse(content={"message": "Shoe Match updated"})


@app.delete("/api/locations/shoe-matches/{sm_id}")
async def delete_shoe_match_endpoint(sm_id: int, current_user: dict = Depends(require_admin_user)):
    """Delete a Shoe Match zone."""
    ok = db.delete_shoe_match(sm_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Shoe Match not found")
    return JSONResponse(content={"message": "Shoe Match deleted"})


@app.post("/api/locations/shelves")
async def create_shelf_endpoint(payload: dict, current_user: dict = Depends(require_admin_user)):
    shoe_match_id = payload.get("shoe_match_id")
    name = payload.get("name", "").strip()
    if not shoe_match_id or not name:
        raise HTTPException(status_code=400, detail="shoe_match_id and shelf name are required")
    res = db.create_shelf(int(shoe_match_id), name)
    return JSONResponse(content={"message": "Shelf created", "data": res}, status_code=201)


@app.put("/api/locations/shelves/{shelf_id}")
async def update_shelf_endpoint(shelf_id: int, payload: dict, current_user: dict = Depends(require_admin_user)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    ok = db.update_shelf(shelf_id, name)
    if not ok:
        raise HTTPException(status_code=404, detail="Shelf not found")
    return JSONResponse(content={"message": "Shelf updated"})


@app.delete("/api/locations/shelves/{shelf_id}")
async def delete_shelf_endpoint(shelf_id: int, current_user: dict = Depends(require_admin_user)):
    ok = db.delete_shelf(shelf_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Shelf not found")
    return JSONResponse(content={"message": "Shelf deleted"})


@app.post("/api/locations/drawers")
async def create_drawer_endpoint(payload: dict, current_user: dict = Depends(require_admin_user)):
    shelf_id = payload.get("shelf_id")
    name = payload.get("name", "").strip()
    if not shelf_id or not name:
        raise HTTPException(status_code=400, detail="shelf_id and drawer name are required")
    res = db.create_drawer(int(shelf_id), name)
    return JSONResponse(content={"message": "Drawer created", "data": res}, status_code=201)


@app.put("/api/locations/drawers/{drawer_id}")
async def update_drawer_endpoint(drawer_id: int, payload: dict, current_user: dict = Depends(require_admin_user)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    ok = db.update_drawer(drawer_id, name)
    if not ok:
        raise HTTPException(status_code=404, detail="Drawer not found")
    return JSONResponse(content={"message": "Drawer updated"})


@app.delete("/api/locations/drawers/{drawer_id}")
async def delete_drawer_endpoint(drawer_id: int, current_user: dict = Depends(require_admin_user)):
    ok = db.delete_drawer(drawer_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Drawer not found")
    return JSONResponse(content={"message": "Drawer deleted"})


@app.post("/api/locations/slots")
async def create_slot_endpoint(payload: dict, current_user: dict = Depends(require_admin_user)):
    drawer_id = payload.get("drawer_id")
    name = payload.get("name", "").strip()
    if not drawer_id or not name:
        raise HTTPException(status_code=400, detail="drawer_id and slot name are required")
    res = db.create_slot(int(drawer_id), name)
    return JSONResponse(content={"message": "Slot created", "data": res}, status_code=201)


@app.put("/api/locations/slots/{slot_id}")
async def update_slot_endpoint(slot_id: int, payload: dict, current_user: dict = Depends(require_admin_user)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    ok = db.update_slot(slot_id, name)
    if not ok:
        raise HTTPException(status_code=404, detail="Slot not found")
    return JSONResponse(content={"message": "Slot updated"})


@app.delete("/api/locations/slots/{slot_id}")
async def delete_slot_endpoint(slot_id: int, current_user: dict = Depends(require_admin_user)):
    ok = db.delete_slot(slot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Slot not found")
    return JSONResponse(content={"message": "Slot deleted"})


@app.post("/api/locations/slots/{slot_id}/assign")
async def assign_slot_endpoint(slot_id: int, payload: dict, current_user: dict = Depends(require_admin_user)):
    """Assign design_id to slot_id, enforcing parent path resolution and flat string synchronization."""
    design_id = payload.get("design_id", "").strip()
    if not design_id:
        raise HTTPException(status_code=400, detail="design_id is required")
    try:
        res = db.assign_design_to_slot(slot_id, design_id)
        return JSONResponse(content=res)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/locations/slots/{slot_id}/unassign")
async def unassign_slot_endpoint(slot_id: int, current_user: dict = Depends(require_admin_user)):
    """Vacate slot_id."""
    ok = db.unassign_slot(slot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Slot not found")
    return JSONResponse(content={"message": "Slot unassigned"})


# Serve Frontend Web App
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

@app.get("/")
async def serve_landing():
    """Serve landing page interface."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse(content={"message": "Shoe Design Matching API running. Frontend not found."})


@app.get("/app")
async def serve_app():
    """Serve main working application interface."""
    app_file = FRONTEND_DIR / "app.html"
    if app_file.exists():
        return FileResponse(
            str(app_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse(content={"message": "Shoe Design Matching API running. App file not found."})
