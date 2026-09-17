import re
from typing import Dict, Any, List, Optional, Tuple
from app.models.udm import Reference

def escape_bibtex(text: str) -> str:
    """Escapes LaTeX special characters in BibTeX field values."""
    if not text:
        return ""
    # Don't escape already escaped chars
    text = re.sub(r'(?<!\\)&', r'\&', text)
    text = re.sub(r'(?<!\\)%', r'\%', text)
    text = re.sub(r'(?<!\\)_', r'\_', text)
    text = re.sub(r'(?<!\\)#', r'\#', text)
    # Replace unicode replacement character  with empty or dash if needed
    text = text.replace('', '')
    return text.strip()

class ReferenceParser:
    @staticmethod
    def parse_reference_line(raw_text: str, index_hint: int, used_keys: set) -> Reference:
        """
        Generically parses a single reference text line into a structured Reference object
        with clean BibTeX entry generation and deterministic cite_key.
        """
        text = raw_text.strip()
        
        # 1. Remove leading [1], 1., (1) numbering
        cleaned_text = re.sub(r'^(?:\[\d+\]|\d+\.|\(\d+\))\s*', '', text)
        
        # 2. Extract DOI and URL
        doi = None
        doi_match = re.search(r'(https?://doi\.org/[^\s]+|10\.\d{4,9}/[^\s]+)', cleaned_text, re.I)
        if doi_match:
            doi = doi_match.group(1).rstrip('.')
            
        url = None
        url_match = re.search(r'https?://[^\s]+', cleaned_text)
        if url_match:
            url = url_match.group(0).rstrip('.')
            
        # 3. Extract Year (4 digits, e.g. (2022) or 2022)
        year = None
        year_match = re.search(r'\((\d{4})[a-z]?\)', cleaned_text)
        if not year_match:
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', cleaned_text)
        if year_match:
            year = year_match.group(1)
            
        # 4. Extract Authors & Title
        authors = []
        primary_surname = "Ref"
        title = None
        journal = None
        
        # Pattern: Author list (YYYY). Title. Journal / Venue
        parts_by_year = re.split(r'\(\d{4}[a-z]?\)\.?', cleaned_text, maxsplit=1)
        if len(parts_by_year) == 2:
            author_part = parts_by_year[0].strip().rstrip('.')
            rest_part = parts_by_year[1].strip()
            
            # Parse authors from author_part
            if author_part:
                # Split by 'and', '&', ','
                raw_authors = re.split(r'\s+and\s+|\s*&\s*', author_part)
                for ra in raw_authors:
                    names = [n.strip() for n in ra.split(',') if n.strip()]
                    if names:
                        authors.append(" ".join(names))
                        
                # Primary surname for citation key
                first_author_str = raw_authors[0].strip() if raw_authors else ""
                first_name_parts = [p.strip() for p in first_author_str.split(',') if p.strip()]
                if first_name_parts:
                    primary_surname = re.sub(r'[^A-Za-z]', '', first_name_parts[0])
                elif author_part:
                    words = [w for w in re.findall(r'[A-Za-z]+', author_part) if len(w) > 1]
                    if words:
                        primary_surname = words[0]

            # Parse title and journal from rest_part
            # Rest part typically: "Title of the paper. Journal Name, Vol, Pages."
            sentences = [s.strip() for s in rest_part.split('.') if s.strip()]
            if sentences:
                title = sentences[0]
                if len(sentences) > 1:
                    journal = ". ".join(sentences[1:])
        else:
            # Fallback title parsing if year split failed
            title = cleaned_text
            words = [w for w in re.findall(r'[A-Za-z]+', cleaned_text) if len(w) > 2]
            if words:
                primary_surname = words[0]

        # Sanitise primary surname
        primary_surname = primary_surname.capitalize() if primary_surname else f"Ref{index_hint}"
        if not primary_surname:
            primary_surname = f"Ref{index_hint}"
            
        # 5. Generate Citation Key
        base_key = f"{primary_surname}{year if year else index_hint}"
        cite_key = base_key
        suffix_char = ord('a')
        while cite_key in used_keys:
            cite_key = f"{base_key}{chr(suffix_char)}"
            suffix_char += 1
        used_keys.add(cite_key)
        
        # 6. Determine BibTeX Entry Type & Construct BibTeX
        entry_type = "article"
        cleaned_lower = cleaned_text.lower()
        if any(kw in cleaned_lower for kw in ["proceedings", "conference", "symposium", "cikm", "icitda", "ieee"]):
            entry_type = "inproceedings"
        elif any(kw in cleaned_lower for kw in ["wikipedia", "online", "available at", "arxiv"]):
            entry_type = "misc"
        elif "book" in cleaned_lower:
            entry_type = "book"
            
        # Build clean BibTeX
        bib_lines = [f"@{entry_type}{{{cite_key},"]
        if authors:
            bib_lines.append(f"  author = {{{escape_bibtex(' and '.join(authors))}}},")
        if title:
            bib_lines.append(f"  title = {{{escape_bibtex(title)}}},")
        if journal:
            if entry_type == "inproceedings":
                bib_lines.append(f"  booktitle = {{{escape_bibtex(journal)}}},")
            else:
                bib_lines.append(f"  journal = {{{escape_bibtex(journal)}}},")
        if year:
            bib_lines.append(f"  year = {{{year}}},")
        if doi:
            bib_lines.append(f"  doi = {{{escape_bibtex(doi)}}},")
        if url and not doi:
            bib_lines.append(f"  url = {{{escape_bibtex(url)}}},")
        if not title and not authors:
            bib_lines.append(f"  note = {{{escape_bibtex(cleaned_text)}}},")
        bib_lines.append("}")
        
        raw_bibtex = "\n".join(bib_lines)
        
        return Reference(
            id=f"ref_{index_hint}",
            cite_key=cite_key,
            title=title or cleaned_text,
            authors=authors,
            journal=journal,
            year=year,
            raw_bibtex=raw_bibtex
        )
