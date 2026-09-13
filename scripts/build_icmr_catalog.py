import httpx
from bs4 import BeautifulSoup
import json
import re

url = "https://www.icmr.gov.in/standard-treatment-workflows-stws"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

with httpx.Client(verify=False, headers=headers, follow_redirects=True, timeout=30.0) as client:
    resp = client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Check accordion structure
    # In Bootstrap/ICMR, specialties are usually card-headers or accordion headers
    stws = []
    
    # Find all accordion cards
    cards = soup.find_all("div", class_="card")
    print(f"Total cards found: {len(cards)}")
    
    for card in cards:
        # Find specialty heading
        header = card.find(["div", "h2", "h3", "h4", "h5", "button"], class_=re.compile(r"header|btn|title", re.I))
        specialty_name = header.get_text(strip=True) if header else "General Medicine"
        # Clean up header
        specialty_name = re.sub(r"[\r\n\t]+", " ", specialty_name).strip()
        
        # Find all pdf links within this card
        links = card.find_all("a", href=True)
        for a in links:
            href = a["href"].strip()
            if href.endswith(".pdf") and "/STWs/" in href:
                text = a.get_text(strip=True)
                parent_text = a.find_parent("li") or a.find_parent("tr") or a.find_parent("div")
                full_text = parent_text.get_text(" ", strip=True) if parent_text else text
                
                # Extract clean disease name
                # e.g., "1 Atrial Fibrillation (43.80 KB) Download" -> "Atrial Fibrillation"
                clean_title = re.sub(r"^\d+\s*", "", full_text)
                clean_title = re.sub(r"\([^)]*\)", "", clean_title)
                clean_title = re.sub(r"\bDownload\b", "", clean_title, flags=re.I).strip()
                
                if not clean_title:
                    clean_title = text or "STW Guideline"
                
                stws.append({
                    "specialty": specialty_name,
                    "disease": clean_title,
                    "pdf_url": href,
                    "raw_text": full_text
                })

    print(f"Total structured STWs mapped: {len(stws)}")
    # Deduplicate by pdf_url
    dedup = {}
    for s in stws:
        if s["pdf_url"] not in dedup:
            dedup[s["pdf_url"]] = s
    unique_stws = list(dedup.values())
    print(f"Unique STWs: {len(unique_stws)}")
    
    with open("data/metadata/icmr_stw_catalog.json", "w", encoding="utf-8") as f:
        json.dump(unique_stws, f, indent=2)
    print("Catalog saved to data/metadata/icmr_stw_catalog.json")
