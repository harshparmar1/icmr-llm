import httpx
import re
from urllib.parse import urljoin

url = "https://www.icmr.gov.in/standard-treatment-workflows-stws"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    with httpx.Client(verify=False, headers=headers, follow_redirects=True, timeout=25.0) as client:
        resp = client.get(url)
        print("Fetched URL status:", resp.status_code)
        content = resp.text
        # Find all pdf links
        pdf_matches = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', content, re.IGNORECASE)
        print(f"Total PDF matches found: {len(pdf_matches)}")
        stw_links = []
        for match in pdf_matches:
            full_url = urljoin(url, match)
            stw_links.append(full_url)
            print("PDF Link:", full_url)

        # Also search for table/links with STW or specialty names
        specialty_matches = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL)
        stw_specialty_links = [
            (urljoin(url, m[0]), re.sub(r'<[^>]+>', '', m[1]).strip())
            for m in specialty_matches
            if "stw" in m[0].lower() or "workflow" in m[1].lower() or "stw" in m[1].lower()
        ]
        print(f"\nTotal STW-related anchors: {len(stw_specialty_links)}")
        for link, title in stw_specialty_links[:20]:
            print(f"  Title: {title} -> Link: {link}")
except Exception as e:
    print("Error querying ICMR portal:", e)
