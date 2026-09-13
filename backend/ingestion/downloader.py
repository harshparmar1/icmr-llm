import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Representative core ICMR STWs across major specialties for baseline ingestion
CORE_STW_TARGETS = [
    {"specialty": "Nephrology", "disease_pattern": "chronic kidney disease|ckd|nephrotic"},
    {"specialty": "Cardiology", "disease_pattern": "heart failure|hypertension|angina|stemi"},
    {"specialty": "Endocrinology", "disease_pattern": "diabetes|diabetic|thyroid"},
    {"specialty": "Pulmonology", "disease_pattern": "asthma|copd|pneumonia"},
    {"specialty": "Neurology", "disease_pattern": "stroke|epilepsy"},
    {"specialty": "Orthopaedics", "disease_pattern": "osteoarthritis|low back pain"},
    {"specialty": "Gastroenterology", "disease_pattern": "cirrhosis|pancreatitis|gerd"},
]


class ICMRDownloader:
    """
    Downloads official ICMR STW PDFs from the verified ICMR portal catalog into data/raw/.
    """

    def __init__(self, target_dir: Optional[Path] = None):
        self.target_dir = Path(target_dir or settings.DATA_RAW_DIR)
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_path = Path(settings.DATA_METADATA_DIR) / "icmr_stw_catalog.json"

    def load_catalog(self) -> List[Dict[str, Any]]:
        """Loads the catalog generated from the live ICMR portal."""
        if not self.catalog_path.exists():
            logger.warning(f"Catalog not found at {self.catalog_path}. Attempting to locate...")
            alt_path = settings.BASE_PATH / "data" / "metadata" / "icmr_stw_catalog.json"
            if alt_path.exists():
                self.catalog_path = alt_path
            else:
                return []

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def download_pdf(self, url: str, destination_name: Optional[str] = None) -> Path:
        """
        Downloads a single official PDF from ICMR with verification.
        """
        if not destination_name:
            destination_name = url.split("/")[-1].split("?")[0]

        dest_file = self.target_dir / destination_name

        # If already downloaded and valid, reuse
        if dest_file.exists() and dest_file.stat().st_size > 1024:
            with open(dest_file, "rb") as f:
                header = f.read(5)
                if header.startswith(b"%PDF"):
                    logger.info(f"File already downloaded and valid: {dest_file.name}")
                    return dest_file

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        logger.info(f"Downloading official ICMR PDF from: {url}")
        with httpx.Client(verify=False, headers=headers, follow_redirects=True, timeout=45.0) as client:
            resp = client.get(url)
            resp.raise_for_status()

            # Verify PDF magic bytes
            if not resp.content.startswith(b"%PDF"):
                raise ValueError(f"Downloaded content from {url} is not a valid PDF header.")

            with open(dest_file, "wb") as f:
                f.write(resp.content)

        logger.info(f"Saved verified ICMR STW PDF: {dest_file.name} ({dest_file.stat().st_size} bytes)")
        return dest_file

    def download_core_dataset(self, max_documents: int = 8) -> List[Dict[str, Any]]:
        """
        Downloads a curated representative cross-specialty sample of official ICMR STWs.
        """
        catalog = self.load_catalog()
        if not catalog:
            logger.error("No catalog available to select STWs.")
            return []

        selected = []
        seen_specialties = set()

        for item in catalog:
            spec = item.get("specialty", "").strip()
            # Try to get 1 representative document per specialty
            if spec not in seen_specialties and len(selected) < max_documents:
                selected.append(item)
                seen_specialties.add(spec)

        downloaded_items = []
        for item in selected:
            try:
                url = item["pdf_url"]
                dest_path = self.download_pdf(url)
                record = dict(item)
                record["local_path"] = str(dest_path.resolve())
                downloaded_items.append(record)
            except Exception as e:
                logger.error(f"Failed to download {item.get('disease')}: {e}")

        logger.info(f"Successfully downloaded {len(downloaded_items)} official ICMR STWs into {self.target_dir}")
        return downloaded_items
