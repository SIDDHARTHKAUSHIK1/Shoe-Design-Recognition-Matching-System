# Shoe Design Recognition & Matching System

A visual search, design fingerprinting, and similarity matching system built for footwear manufacturing and design verification teams.

---

## System Architecture

```
┌─────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│  Upload Image   │─────▶│     Embedding Engine    │─────▶│    Vector Store (FAISS) │
│ (Query / Admin) │      │  (Meta DINOv2 / CLIP)   │      │  (IndexFlatIP Cosine)   │
└─────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                       │
                                                           ┌───────────▼────────────┐
                                                           │  Top-3 Ranked Matcher  │
                                                           │ (Cosine Sim + Aggreg)  │
                                                           └───────────┬────────────┘
                                                                       │
                                                           ┌───────────▼────────────┐
                                                           │  FastAPI & Web Studio  │
                                                           │ (Side-by-Side Ratings) │
                                                           └────────────────────────┘
```

### Key Technical Decisions
1. **Embedding Model**: Meta **DINOv2 (`facebook/dinov2-small`)** extracting 384-dimensional $L_2$-normalized vectors with **~100ms CPU latency**. DINOv2 was chosen for its fine-grained representation of silhouette curves, upper stitching, sole patterns, and textures without requiring training from scratch.
2. **Vector Index**: **FAISS `IndexFlatIP`** (Exact Inner Product on normalized vectors $\equiv$ exact cosine similarity).
3. **Incremental Growth**: Adding a new design uses `index.add()` in $O(1)$ time without requiring a full catalog rebuild.
4. **Metadata & Audit Store**: SQLite database in WAL mode tracking catalog designs, multi-angle reference photos, and query audit history.
5. **No Hard Auto-Reject Cutoff**: Returns the **Top 3 Ranked Matches** (Best, Second-Best, Third-Best) with accuracy percentages and visual color coding:
   - 🟢 **High Match** ($\ge 85\%$): Strong visual match to catalog design.
   - 🟡 **Moderate Match** ($70\% - 84.9\%$): Likely design variant, family silhouette, or colorway.
   - 🔴 **Low Similarity / Novel** ($< 70\%$): Distinct or novel shoe design.

---

## Accuracy & Evaluation Benchmark

Leave-One-Out (LOO) cross-validation on catalog reference photos:

| Metric | Result | Benchmark Target |
| :--- | :--- | :--- |
| **Top-1 Accuracy** | **97.92%** | $> 90\%$ |
| **Top-3 Accuracy** | **100.00%** | $> 98\%$ |
| **Mean Reciprocal Rank (MRR)** | **0.9896** | $> 0.95$ |
| **Avg Query Latency** | **< 100 ms** | $< 2000\text{ ms}$ |
| **Avg Same-Design Cosine Similarity** | **96.9%** | High match zone |
| **Avg Cross-Design Cosine Similarity** | **67.4%** | Low similarity zone |
| **Separation Margin** | **+29.5%** | Robust decision gap |

---

## Project Structure

```
Shoe_Design_Detection/
├── dataset/                  # Initial raw shoe photos
├── backend/
│   ├── config.py             # System paths, model parameters, thresholds
│   ├── database.py           # SQLite catalog, reference images, and query logs
│   ├── engine.py             # DINOv2 feature extractor with singleton lifecycle
│   ├── vector_store.py       # FAISS IndexFlatIP wrapper with atomic persistence
│   ├── matcher.py            # Top-3 ranking, score computation, and multi-angle aggregation
│   ├── ingestion.py          # Automatic dataset scanner and incremental indexer
│   └── main.py               # FastAPI application with REST endpoints and static serving
├── frontend/
│   ├── index.html            # Web Studio interface
│   ├── styles.css            # Responsive vanilla CSS design system
│   └── app.js                # Drag-and-drop upload, match renderer, and catalog manager
├── storage/                  # SQLite DB, serialized FAISS index, and image assets
├── evaluate.py               # Evaluation benchmark script
├── run_server.py             # Server launcher
├── Dockerfile                # Production container spec
└── docker-compose.yml        # Docker compose deployment
```

---

## Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Ingest Reference Catalog
```bash
python -m backend.ingestion
```

### 3. Run Benchmark Evaluation
```bash
python evaluate.py
```

### 4. Start Server & Open Web Studio
```bash
python run_server.py
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## REST API Documentation

### 1. Match Shoe Photo
- **Endpoint**: `POST /api/match`
- **Payload**: `multipart/form-data` with `file: <binary image>`, `top_k: 3`
- **Response**:
```json
{
  "success": true,
  "query_image_path": "/uploads/query_1718000000_shoe.jpg",
  "total_catalog_designs": 23,
  "total_catalog_vectors": 48,
  "latency_ms": 88.5,
  "matches": [
    {
      "rank": 1,
      "design_id": "SHOE-001",
      "design_name": "AeroStride Pro Runner",
      "category": "Sneaker",
      "confidence_pct": 98.4,
      "cosine_similarity": 0.984,
      "match_level": "HIGH",
      "match_level_label": "High Confidence Match",
      "match_color": "green",
      "best_matching_angle": "side",
      "best_matching_image_url": "/catalog_images/SHOE-001/angle_side_1.jpg",
      "all_angles": [...]
    },
    ...
  ]
}
```

### 2. Add New Design (Incremental Add)
- **Endpoint**: `POST /api/designs`
- **Payload**: `multipart/form-data`
  - `design_id`: "SHOE-024"
  - `name`: "Urban Glide High-Top"
  - `category`: "Sneaker"
  - `description`: "Rubber cupsole with mesh upper"
  - `created_by`: "Design Team"
  - `files`: Multiple image files

### 3. List Designs
- **Endpoint**: `GET /api/designs`

### 4. Audit History Logs
- **Endpoint**: `GET /api/logs?limit=50`

### 5. Benchmark On-Demand
- **Endpoint**: `POST /api/evaluate`

---

## Running with Docker

```bash
docker-compose up --build
```
Access the application at `http://localhost:8000`.
