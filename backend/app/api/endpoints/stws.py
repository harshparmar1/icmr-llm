import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Standard Treatment Workflows"])


@router.get("/stws", summary="List Available ICMR Standard Treatment Workflows")
def list_stws(
    specialty_id: Optional[int] = None,
    disease_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Returns the list of active ICMR Standard Treatment Workflow documents from Supabase.
    """
    query = db.query(STWDocument).filter(STWDocument.is_active == True)
    if specialty_id:
        query = query.filter(STWDocument.specialty_id == specialty_id)
    if disease_id:
        query = query.filter(STWDocument.disease_id == disease_id)

    stws = query.all()
    results = []
    for doc in stws:
        results.append({
            "id": doc.id,
            "title": doc.title,
            "specialty_id": doc.specialty_id,
            "specialty_name": doc.specialty.name if doc.specialty else None,
            "disease_id": doc.disease_id,
            "disease_name": doc.disease.name if doc.disease else None,
            "volume": doc.volume,
            "edition": doc.edition,
            "total_pages": doc.total_pages,
            "official_url": doc.official_icmr_url
        })
    return results


@router.get("/specialties", summary="List ICMR Clinical Specialties")
def list_specialties(db: Session = Depends(get_db)):
    """
    Returns all indexed medical specialties along with their disease counts.
    """
    specialties = db.query(Specialty).order_by(Specialty.name.asc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "description": s.description,
            "disease_count": len(s.diseases),
            "stw_count": len(s.stw_documents)
        }
        for s in specialties
    ]


@router.get("/diseases", summary="List Indexed Diseases and Conditions")
def list_diseases(specialty_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Returns all indexed clinical conditions, optionally filtered by specialty.
    """
    query = db.query(Disease).order_by(Disease.name.asc())
    if specialty_id:
        query = query.filter(Disease.specialty_id == specialty_id)

    diseases = query.all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "code": d.code,
            "icd10_code": d.icd10_code,
            "specialty_id": d.specialty_id,
            "specialty_name": d.specialty.name if d.specialty else None,
            "description": d.description
        }
        for d in diseases
    ]


@router.get("/suggestions", summary="Quick Clinical Workflow Suggestions")
def get_clinical_suggestions():
    """
    Returns quick-query suggestions for common clinical conditions covered in ICMR STWs.
    """
    return [
        {
            "label": "Hyperkalemia in AKI",
            "specialty": "Nephrology",
            "query": "How to treat emergency hyperkalemia in Acute Kidney Injury according to ICMR guidelines?",
            "context": "Serum K+ 6.8 mEq/L, ECG shows tall peaked T waves, eGFR 22 mL/min",
            "icon": "fa-heart-pulse"
        },
        {
            "label": "Hypertension Stage 1",
            "specialty": "Cardiology",
            "query": "What is the initial pharmacological stepped-care protocol for Stage 1 Hypertension in adults?",
            "context": "BP 146/94 mmHg confirmed over 2 visits, non-diabetic, age 48",
            "icon": "fa-stethoscope"
        },
        {
            "label": "Acute Rhinosinusitis",
            "specialty": "ENT",
            "query": "What are the diagnostic criteria and antibiotic indication rules for Acute Rhinosinusitis?",
            "context": "Purulent nasal discharge and facial pain for 12 days, 'double sickening'",
            "icon": "fa-head-side-cough"
        },
        {
            "label": "Atrial Fibrillation Rate Control",
            "specialty": "Cardiology",
            "query": "What is the acute rate control workflow for hemodynamically stable Atrial Fibrillation?",
            "context": "Heart rate 138 bpm, BP 122/78 mmHg, no heart failure history",
            "icon": "fa-wave-square"
        },
        {
            "label": "Acute Encephalitis Protocol",
            "specialty": "Paediatrics",
            "query": "Initial emergency triage and empiric antimicrobial protocol for child presenting with Acute Encephalitis Syndrome?",
            "context": "Age 6 years, acute onset fever, altered sensorium, generalized seizures",
            "icon": "fa-child"
        }
    ]
