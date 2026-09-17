import re
from typing import List, Tuple, Dict, Any, Optional
from app.models.udm import Reference

class CitationMatcher:
    @staticmethod
    def match_references(author_surname: str, year: str, references: List[Reference]) -> Optional[Reference]:
        """
        Finds the matching Reference object from references list based on author surname and year.
        """
        surname_clean = re.sub(r'[^A-Za-z]', '', author_surname).lower()
        if not surname_clean:
            return None

        # 1. Exact match by cite_key prefix & year
        for ref in references:
            ref_key_lower = ref.cite_key.lower()
            if surname_clean in ref_key_lower and (not year or (ref.year and year in ref.year)):
                return ref

        # 2. Match by ref.authors or ref.title
        for ref in references:
            if year and ref.year and year not in ref.year:
                continue
            ref_str = (ref.title + " " + " ".join(ref.authors) + " " + (ref.raw_bibtex or "")).lower()
            if surname_clean in ref_str:
                return ref

        # 3. Fallback: match surname alone if unique
        if surname_clean and surname_clean != "ref":
            surname_matches = []
            for ref in references:
                ref_str = (ref.cite_key + " " + ref.title + " " + " ".join(ref.authors)).lower()
                if surname_clean in ref_str:
                    surname_matches.append(ref)
            if len(surname_matches) == 1:
                return surname_matches[0]

        return None

    @staticmethod
    def process_paragraph_text(text: str, references: List[Reference]) -> Tuple[str, List[str]]:
        """
        Scans paragraph text for author-year citation patterns and replaces matched
        citations with appropriate LaTeX \\cite{cite_key} commands.
        Returns (updated_text, list_of_matched_keys).
        """
        if not text or not references:
            return text, []

        matched_keys = []
        updated_text = text

        # 1. Parenthetical Citations: (Author et al, 2018), (Author & Author, 2021), (Author, 2022)
        # e.g. (Singh et al, 2018) -> \cite{Singh2018}
        paren_pattern = re.compile(
            r'\(([A-Z][A-Za-z\-]+(?:\s+et\s+al\.?|\s+and\s+[A-Z][A-Za-z\-]+|\s*,\s*[A-Z][A-Za-z\-]+)?)\s*,?\s*(\d{4}[a-z]?)\)'
        )

        def replace_paren(match):
            author_part = match.group(1).strip()
            year_part = match.group(2).strip()
            primary_surname = re.split(r'\s+et\s+al|\s+and|\s*,', author_part)[0].strip()
            matched_ref = CitationMatcher.match_references(primary_surname, year_part, references)
            if matched_ref:
                matched_keys.append(matched_ref.cite_key)
                return f"\\cite{{{matched_ref.cite_key}}}"
            return match.group(0)

        updated_text = paren_pattern.sub(replace_paren, updated_text)

        # 2. Narrative/Prose Citations: Author et al. (2022), Author and Author (2021), Author (2022)
        # e.g. Pramana et al. (2022) -> Pramana et al. \cite{Pramana2022}
        prose_pattern = re.compile(
            r'\b([A-Z][A-Za-z\-]+(?:\s+et\s+al\.?|\s+and\s+[A-Z][A-Za-z\-]+)?)\s*\((19\d{2}|20\d{2}[a-z]?)\)'
        )

        def replace_prose(match):
            author_part = match.group(1).strip()
            year_part = match.group(2).strip()
            primary_surname = re.split(r'\s+et\s+al|\s+and', author_part)[0].strip()
            matched_ref = CitationMatcher.match_references(primary_surname, year_part, references)
            if matched_ref:
                matched_keys.append(matched_ref.cite_key)
                return f"{author_part} \\cite{{{matched_ref.cite_key}}}"
            return match.group(0)

        updated_text = prose_pattern.sub(replace_prose, updated_text)

        # 3. Numbered Citations: [1], [1, 2], [1-3]
        num_pattern = re.compile(r'\[(\d+(?:\s*[\,\-\–\—]\s*\d+)*)\]')

        def replace_num(match):
            content = match.group(1)
            nums = []
            for part in re.split(r'[,]', content):
                part = part.strip()
                m_range = re.match(r'^(\d+)\s*[\-\–\—]\s*(\d+)$', part)
                if m_range:
                    start_i, end_i = int(m_range.group(1)), int(m_range.group(2))
                    if start_i <= end_i:
                        nums.extend(range(start_i, end_i + 1))
                elif part.isdigit():
                    nums.append(int(part))
                    
            keys = []
            for n in nums:
                if 1 <= n <= len(references):
                    keys.append(references[n-1].cite_key)
                    matched_keys.append(references[n-1].cite_key)
                else:
                    return match.group(0)
                    
            if keys:
                return '\\cite{' + ','.join(keys) + '}'
            return match.group(0)

        updated_text = num_pattern.sub(replace_num, updated_text)

        return updated_text, matched_keys
