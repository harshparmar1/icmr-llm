import re
import unicodedata
from typing import Tuple, Optional


class ClinicalTextCleaner:
    """
    Cleans raw text extracted from ICMR STW documents:
    - Normalizes unicode characters
    - Repairs hyphenated word splits across line breaks
    - Removes recurrent ICMR legal footers and disclaimer boilerplate
    - Standardizes clinical list bullets
    - Normalizes multi-whitespace while preserving clinical structure
    """

    # Disclaimers and boilerplate patterns in ICMR STWs
    DISCLAIMER_PATTERNS = [
        r"This STW has been prepared by national experts of India.*?(?=Kindly visit|$)",
        r"©\s*Indian Council of Medical Research.*?Government of India\.?",
        r"Department of Health Research\s+Ministry of Health and Family Welfare.*",
        r"Kindly visit our web portal\s*\(stw\.icmr\.org\.in\)\s*for more information\.?",
        r"There will be no indemnity for direct or indirect consequences\.?",
        r"Ministry of Health & Family Welfare, Government of India\.?",
        r"National Health Mission.*?Government of India\.?",
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)[\s/]+20\d\d"
    ]

    def __init__(self):
        self._compiled_disclaimers = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in self.DISCLAIMER_PATTERNS
        ]

    def clean_page_text(self, text: str) -> str:
        """
        Executes the full cleaning pipeline on a single page's text.
        """
        if not text:
            return ""

        # 1. Unicode Normalization
        text = unicodedata.normalize("NFKD", text)

        # 2. Repair hyphenated words broken by line wraps (e.g. creati-\nnine -> creatinine)
        text = re.sub(r"(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)", r"\1\2", text)
        text = re.sub(r"(\b[a-zA-Z]+)-\s*\n\s*([0-9a-zA-Z]+/[a-zA-Z]+)", r"\1\2", text)  # e.g., k-\ng/h

        # 3. Strip legal disclaimers and footer noise
        for pattern in self._compiled_disclaimers:
            text = pattern.sub("", text)

        # 4. Standardize bullet characters
        text = re.sub(r"[\u2022\u2023\u25E6\u2043\u2219\u25CF\u25CB\u25AA\u25A0]\s*", "• ", text)

        # 5. Clean up line artifacts
        lines = []
        for line in text.split("\n"):
            cleaned_line = " ".join(line.split())
            if cleaned_line:
                lines.append(cleaned_line)

        cleaned_text = "\n".join(lines)

        # 6. Normalize excessive blank lines
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

        return cleaned_text

    def extract_icd_code(self, text: str) -> Optional[str]:
        """
        Extracts ICD-11 or ICD-10 code if present in the document.
        """
        match = re.search(r"\b(ICD-(?:10|11)[-:\s]+[A-Z0-9\.]+)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None
