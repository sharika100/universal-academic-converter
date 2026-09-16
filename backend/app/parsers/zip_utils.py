import os
import re
from typing import Dict, List, Any, Optional, Tuple

def build_directory_tree(base_dir: str) -> List[Dict[str, Any]]:
    """Builds a hierarchical tree representation of files in base_dir."""
    tree = []
    
    for root, dirs, files in os.walk(base_dir):
        rel_root = os.path.relpath(root, base_dir)
        if rel_root == ".":
            rel_root = ""
            
        for f in files:
            rel_path = os.path.join(rel_root, f).replace("\\", "/")
            ext = os.path.splitext(f)[1].lower()
            kind = "file"
            if ext in [".tex", ".sty", ".cls", ".bst", ".bib"]:
                kind = "code"
            elif ext in [".png", ".jpg", ".jpeg", ".pdf", ".eps"]:
                kind = "image"
            elif ext == ".docx":
                kind = "docx"
            elif ext == ".zip":
                kind = "zip"
                
            tree.append({
                "path": rel_path,
                "name": f,
                "type": kind,
                "size": os.path.getsize(os.path.join(root, f))
            })
            
    return tree

def find_latex_entrypoint(base_dir: str) -> Tuple[Optional[str], List[str], List[str]]:
    """
    Finds main entrypoint .tex file containing \\documentclass in base_dir using dynamic scoring.
    Returns (primary_entrypoint, list_of_candidate_entrypoints, list_of_all_tex_files).
    """
    all_tex = []
    candidates = []
    scores = {}

    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".tex"):
                rel_path = os.path.relpath(os.path.join(root, f), base_dir).replace("\\", "/")
                all_tex.append(rel_path)

                full_path = os.path.join(root, f)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()

                    if r"\documentclass" in content:
                        candidates.append(rel_path)
                        score = 100
                        
                        f_lower = f.lower()
                        rel_lower = rel_path.lower()

                        if r"\begin{document}" in content and r"\end{document}" in content:
                            score += 200

                        if f_lower in ["main.tex", "paper.tex", "manuscript.tex", "article.tex"]:
                            score += 150

                        # Penalize template/sample/documentation files
                        if any(kw in f_lower or kw in rel_lower for kw in ["template", "sample", "elsdoc", "coverletter", "readme", "guideline"]):
                            score -= 350

                        # Title quality check
                        title_m = re.search(r'\\title(?:\[[^\]]*\])?\{([^}]+)\}', content, re.DOTALL)
                        if title_m:
                            t_text = title_m.group(1).strip()
                            if not any(kw in t_text.lower() for kw in ["template", "sample", "short title", "elsdoc"]):
                                score += 200

                        if r"\author" in content:
                            score += 100

                        sec_count = len(re.findall(r'\\section\*?\{', content))
                        score += min(sec_count * 50, 300)

                        if r"\bibliography" in content or r"\addbibresource" in content or r"\begin{thebibliography}" in content:
                            score += 100

                        score += len(content) // 200
                        scores[rel_path] = score
                except Exception:
                    pass

    # Sort candidates by score descending
    candidates.sort(key=lambda c: scores.get(c, 0), reverse=True)
    primary = candidates[0] if candidates else (all_tex[0] if all_tex else None)

    return primary, candidates, all_tex

def summarize_latex_project(base_dir: str) -> Dict[str, Any]:
    """Inspects a LaTeX project directory and extracts a structured summary report."""
    primary, candidates, all_tex = find_latex_entrypoint(base_dir)
    
    cls_files = []
    bib_files = []
    sty_files = []
    bst_files = []
    figures = []
    other_files = []
    total_size = 0
    total_files = 0
    
    for root, _, files in os.walk(base_dir):
        for f in files:
            total_files += 1
            full_p = os.path.join(root, f)
            sz = os.path.getsize(full_p)
            total_size += sz
            rel_path = os.path.relpath(full_p, base_dir).replace("\\", "/")
            ext = os.path.splitext(f)[1].lower()
            
            if ext == ".cls":
                cls_files.append(rel_path)
            elif ext == ".bib":
                bib_files.append(rel_path)
            elif ext == ".sty":
                sty_files.append(rel_path)
            elif ext == ".bst":
                bst_files.append(rel_path)
            elif ext in [".png", ".jpg", ".jpeg", ".pdf", ".eps"]:
                figures.append(rel_path)
            elif ext not in [".tex"]:
                other_files.append(rel_path)
                
    alt_tex = [t for t in candidates if t != primary]
    
    return {
        "main_tex": primary,
        "alt_tex": alt_tex,
        "all_tex": all_tex,
        "cls_files": cls_files,
        "bib_files": bib_files,
        "sty_files": sty_files,
        "bst_files": bst_files,
        "figures": figures,
        "other_files": other_files[:10], # Truncate long list for presentation
        "total_files": total_files,
        "total_size_bytes": total_size
    }
