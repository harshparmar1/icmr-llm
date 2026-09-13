# ICMR-STW AI: Database Architecture & Schema Design

## 1. Dual-Store Philosophy

To ensure fast query latency, strict relational integrity, and deep semantic retrieval, ICMR-STW AI employs a **Dual-Store Strategy**:
1. **Relational Database (PostgreSQL / SQLite)**: Stores structured clinical metadata, disease taxonomies, discrete workflow steps, and audit logs.
2. **Vector Database (ChromaDB)**: Stores high-dimensional dense embeddings of text chunks with metadata filters for fast semantic search.

---

## 2. Relational Schema (SQLAlchemy ORM)

```mermaid
erDiagram
    SPECIALTIES ||--o{ DISEASES : contains
    SPECIALTIES ||--o{ STW_DOCUMENTS : categorizes
    DISEASES ||--o{ STW_DOCUMENTS : references
    DISEASES ||--o{ WORKFLOW_STEPS : defines
    STW_DOCUMENTS ||--o{ WORKFLOW_STEPS : details
    QUERY_LOGS ||--o{ QUERY_SOURCES : logs
    STW_DOCUMENTS ||--o{ QUERY_SOURCES : cited_in

    SPECIALTIES {
        int id PK
        string code UK
        string name UK
        text description
        datetime created_at
    }

    DISEASES {
        int id PK
        int specialty_id FK
        string code UK
        string name
        string icd10_code
        text description
        datetime created_at
    }

    STW_DOCUMENTS {
        int id PK
        int specialty_id FK
        int disease_id FK
        string title
        string volume
        string edition
        string official_icmr_url
        string file_path
        int total_pages
        int publication_year
        text summary
        bool is_active
        datetime created_at
    }

    WORKFLOW_STEPS {
        int id PK
        int stw_document_id FK
        int disease_id FK
        int step_number
        string phase
        string title
        text description
        text mandatory_actions
        text contraindications
        text red_flags
        int page_reference
        string icmr_section
        datetime created_at
    }

    QUERY_LOGS {
        int id PK
        text query_text
        int specialty_id FK
        int disease_id FK
        int retrieved_stw_id FK
        text response_summary
        string llm_provider
        float latency_ms
        bool is_grounded
        datetime created_at
    }

    QUERY_SOURCES {
        int id PK
        int query_log_id FK
        int stw_document_id FK
        string chunk_id
        int page_number
        string section
        float similarity_score
        text excerpt
    }
```

---

## 3. Vector Database Collection (ChromaDB)

- **Collection Name**: `icmr_stw_chunks`
- **Embedding Space**: 384 dimensions (`all-MiniLM-L6-v2`) or 768 dimensions (`bge-base-en-v1.5`)
- **Metadata Fields Attached to Every Vector**:
  - `document_id`: Integer foreign key matching `stw_documents.id`
  - `specialty_code`: String code (e.g., `NEPHRO`)
  - `disease_code`: String code (e.g., `CKD`)
  - `disease_name`: String name (e.g., `Chronic Kidney Disease`)
  - `volume`: String volume label (e.g., `Volume 1`)
  - `page_number`: Integer source PDF page
  - `section`: Identified clinical section (e.g., `Initial Assessment`)
  - `chunk_index`: Sequence offset within the document
  - `chunk_id`: Unique identifier string (e.g., `ICMR-CKD-P04-C02`)
