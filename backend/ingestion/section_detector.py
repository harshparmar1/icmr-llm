import re
from typing import List, Dict, Tuple
from backend.ingestion.models import ClinicalSection


class ClinicalSectionDetector:
    """
    Identifies and segments clinical sections in ICMR STW documents:
    - Assessment & Clinical Presentation
    - Diagnostic Investigations & Staging
    - Primary / Secondary / Tertiary Care Management
    - Red Flags & Emergency Referral Triggers
    - Follow-up & Monitoring
    """

    # Defined section types and their matching header patterns
    SECTION_RULES: List[Tuple[str, str, re.Pattern]] = [
        # (section_type, default_title, regex)
        ("RED_FLAGS", "Red Flags & Urgent Referral", re.compile(
            r"^(?:RED\s*FLAGS(?:\s*FOR\s*URGENT\s*REFERRAL)?|CRITICAL\s*SIGNS|EMERGENCY\s*SIGNS|INDICATIONS\s*FOR\s*DIALYSIS|INDICATIONS\s*FOR\s*URGENT\s*REFERRAL)[:\s]*$",
            re.IGNORECASE
        )),
        ("INVESTIGATION", "Investigations & Diagnostic Staging", re.compile(
            r"^(?:DESIRABLE\s*ACTIONS[/\s]*INVESTIGATIONS|INVESTIGATIONS|DIAGNOSTIC\s*CRITERIA|LABORATORY\s*INVESTIGATIONS|DIAGNOSIS|STAGING(?:\s*OF\s*[A-Z]+)?|WORKUP)[:\s]*$",
            re.IGNORECASE
        )),
        ("ASSESSMENT", "Initial Assessment & Principles", re.compile(
            r"^(?:PRINCIPLES\s*OF\s*ASSESSMENT|PRELIMINARY\s*ACTIONS|INITIAL\s*ASSESSMENT|CLINICAL\s*EVALUATION|HISTORY\s*AND\s*PHYSICAL\s*EXAMINATION|INITIAL\s*EVALUATION)[:\s]*$",
            re.IGNORECASE
        )),
        ("MANAGEMENT", "Primary Care Management", re.compile(
            r"^(?:PRIMARY\s*CARE|INITIAL\s*MANAGEMENT|TREATMENT\s*OF\s*[A-Z\s]+|PHARMACOLOGICAL\s*MANAGEMENT|PHARMACOTHERAPY|MANAGEMENT|TREATMENT)[:\s]*$",
            re.IGNORECASE
        )),
        ("MANAGEMENT", "Secondary Care Management", re.compile(
            r"^(?:SECONDARY\s*CARE|HOSPITAL\s*MANAGEMENT)[:\s]*$",
            re.IGNORECASE
        )),
        ("MANAGEMENT", "Tertiary Care Management", re.compile(
            r"^(?:TERTIARY\s*CARE|SPECIALIZED\s*MANAGEMENT)[:\s]*$",
            re.IGNORECASE
        )),
        ("FOLLOW_UP", "Follow-Up & Monitoring", re.compile(
            r"^(?:FOLLOW-UP(?:\s*OF\s*[A-Z\s]+)?|MONITORING|PROGNOSIS|DISCHARGE\s*CRITERIA)[:\s]*$",
            re.IGNORECASE
        )),
        ("OVERVIEW", "Definition & Risk Factors", re.compile(
            r"^(?:WHAT\s*IS\s*[A-Z\s\?]+|DEFINITION|AKI\s*RISK\s*INCREASES\s*IN\s*THE\s*PRESENCE\s*OF|RISK\s*FACTORS|SYMPTOMS|CLINICAL\s*FEATURES|EPIDEMIOLOGY)[:\s]*$",
            re.IGNORECASE
        )),
        ("REFERENCES", "Abbreviations & References", re.compile(
            r"^(?:ABBREVIATIONS|REFERENCES|REFERENCE)[:\s]*$",
            re.IGNORECASE
        )),
    ]

    def detect_sections(self, page_text: str, page_number: int) -> List[ClinicalSection]:
        """
        Segments page text into clinical sections based on recognized headers.
        """
        if not page_text or not page_text.strip():
            return []

        lines = [line.strip() for line in page_text.split("\n") if line.strip()]
        
        # Track header matches: (line_index, section_type, detected_title)
        header_indices: List[Tuple[int, str, str]] = []

        for idx, line in enumerate(lines):
            # Check if line matches any section header rule
            for sec_type, default_title, pattern in self.SECTION_RULES:
                if pattern.match(line):
                    header_indices.append((idx, sec_type, line))
                    break

        # If no explicit headers were identified, return entire page as GENERAL section
        if not header_indices:
            return [
                ClinicalSection(
                    title="General Clinical Guidance",
                    section_type="GENERAL",
                    content=page_text.strip(),
                    page_number=page_number,
                    char_count=len(page_text.strip())
                )
            ]

        sections: List[ClinicalSection] = []

        # Content before the first matched header (e.g. title, definition, introduction)
        first_idx = header_indices[0][0]
        if first_idx > 0:
            pre_header_content = "\n".join(lines[:first_idx]).strip()
            if pre_header_content:
                sections.append(
                    ClinicalSection(
                        title="Overview & Clinical Definition",
                        section_type="OVERVIEW",
                        content=pre_header_content,
                        page_number=page_number,
                        char_count=len(pre_header_content)
                    )
                )

        # Process each detected section
        for i, (start_idx, sec_type, title) in enumerate(header_indices):
            # Determine section end index
            if i + 1 < len(header_indices):
                end_idx = header_indices[i + 1][0]
            else:
                end_idx = len(lines)

            # Extract content lines (excluding header itself)
            content_lines = lines[start_idx + 1:end_idx]
            content = "\n".join(content_lines).strip()

            if content:
                sections.append(
                    ClinicalSection(
                        title=title.title(),
                        section_type=sec_type,
                        content=content,
                        page_number=page_number,
                        char_count=len(content)
                    )
                )

        return sections
