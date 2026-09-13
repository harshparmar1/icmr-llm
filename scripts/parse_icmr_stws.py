import httpx
import re
from bs4 import BeautifulSoup

url = "https://www.icmr.gov.in/standard-treatment-workflows-stws"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

with httpx.Client(verify=False, headers=headers, follow_redirects=True, timeout=25.0) as client:
    resp = client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Check accordion items or sections
    cards = soup.find_all("div", class_=lambda c: c and ("card" in c or "accordion" in c or "tab" in c))
    print("Found potential cards/sections:", len(cards))
    
    # Search for all links with pdf
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.endswith(".pdf") and "/STWs/" in href:
            text = a.get_text(strip=True)
            # Find closest heading or parent container
            parent = a.find_parent(["tr", "li", "div", "section"])
            context = parent.get_text(strip=True, separator=" ") if parent else ""
            results.append((href, text, context[:120]))
            
    print(f"Total /STWs/ PDF links: {len(results)}")
    for r in results[:20]:
        print(f"URL: {r[0]}\n  Context: {r[2]}\n")
