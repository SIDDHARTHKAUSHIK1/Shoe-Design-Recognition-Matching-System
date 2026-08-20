"""
FastAPI Application Backend for Shoe Design Recognition & Matching System.
"""
import os
import time
import shutil
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
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
async def list_designs():
    """Retrieve all catalog shoe designs with thumbnails and image counts."""
    designs = db.get_all_designs()
    return JSONResponse(content={"total": len(designs), "designs": designs})


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
async def get_logs(limit: int = 50):
    """Retrieve recent query audit logs."""
    logs = db.get_query_logs(limit=limit)
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
