# ICMR-STW AI: Data Pipeline & Intelligent Chunking Architecture

## 1. Overview

The **ICMR-STW AI Data Pipeline** transforms raw, multi-column clinical guideline PDFs from the **Indian Council of Medical Research (ICMR)** into structured, section-bounded, evidence-grounded chunks suitable for dense vector embedding and hybrid retrieval.

---

## 2. End-to-End Ingestion & Chunking Flow

```
[Official ICMR STW PDFs] (data/raw/)
          │
          ▼
 [PDF Extraction Engine] (PyMuPDF + Unicode NFKD + OCR Fallback)
          │
          ▼
[Structured Page Storage] (data/processed/*_extracted.json)
          │
          ▼
 [Clinical Text Cleaning] (Hyphenation repair, disclaimer stripping, bullet normalization)
          │
          ▼
[Section Classification] (OVERVIEW, ASSESSMENT, INVESTIGATION, MANAGEMENT, RED_FLAGS, FOLLOW_UP)
          │
          ▼
 [Section-Bounded Chunking] (Clinical coherence preservation, sliding-window overlap)
          │
          ▼
[Context Header & Metadata Injection]
 [ICMR STW: {disease} | Specialty: {specialty} | Section: {section} | Page: {page}]
          │
          ▼
[Master Chunk Dataset] (data/processed/icmr_clinical_chunks.json)
```

---

## 3. Core Pipeline Modules

### 3.1 Clinical Text Cleaner (`backend/ingestion/text_cleaner.py`)
- **Hyphenation Repair**: Accurately re-joins clinical terms split by line wraps (e.g., `creati-\nnine` -> `creatinine`, `k-\ng/h` -> `kg/h`).
- **Boilerplate Stripping**: Removes recurring ICMR legal disclaimers, publication dates, and ministry portal footers that would otherwise pollute embedding representations.
- **Bullet & Whitespace Normalization**: Normalizes varied unicode bullet styles and multi-line breaks.

### 3.2 Clinical Section Detector (`backend/ingestion/section_detector.py`)
Classifies content into standard clinical decision-support categories:
1. **`OVERVIEW`**: Disease definitions, diagnostic thresholds, risk factor lists.
2. **`ASSESSMENT`**: Clinical evaluation principles, preliminary emergency actions.
3. **`INVESTIGATION`**: Laboratory workup, diagnostic staging criteria, imaging.
4. **`MANAGEMENT`**: Primary care, secondary care, and tertiary care pharmacological & non-pharmacological interventions.
5. **`RED_FLAGS`**: Critical referral triggers, emergency indicators (e.g. indications for urgent dialysis).
6. **`FOLLOW_UP`**: Long-term monitoring schedules, recovery criteria.
7. **`REFERENCES`**: Abbreviation tables and authoritative citations.

### 3.3 Section-Aware Chunker (`backend/ingestion/chunker.py`)
- **Clinical Coherence Rule**: If a clinical section is within the target threshold (<= 750 characters), it is kept intact as a single atomic unit to avoid fragmenting diagnostic or treatment steps.
- **Sliding-Window Fallback**: For lengthy sections, splits on paragraph/sentence boundaries with 120-character overlap.
- **Context Injection**: Prepends an explicit clinical breadcrumb to every chunk before embedding:
  ```
  [ICMR STW: Acute Kidney Injury | Specialty: Nephrology | Section: Treatment Of Hyperkalemia (MANAGEMENT) | Page: 1]
  ```
- **Deterministic Chunk IDs**: Format: `ICMR-{SPECIALTY}-{DISEASE}-P{PAGE:02d}-C{INDEX:03d}` (e.g., `ICMR-NEPHRO-ACUTEKID-P01-C007`).

---

## 4. Execution Commands

### Extracting & Ingesting Raw PDFs:
```powershell
python scripts/run_ingestion.py
```

### Running Clinical Cleaning, Section Detection & Chunking:
```powershell
python scripts/run_chunking.py
```

### Running Unit Tests:
```powershell
python -m pytest backend/tests -v
```
