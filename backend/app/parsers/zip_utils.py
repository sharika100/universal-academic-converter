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
    Finds main entrypoint .tex file containing \\documentclass in base_dir.
    Returns (primary_entrypoint, list_of_candidate_entrypoints, list_of_all_tex_files).
    """
    all_tex = []
    candidates = []
    primary = None
    
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
                            if f.lower() in ["main.tex", "paper.tex", "manuscript.tex", "bare_conf.tex", "eaamrwithauthor.tex"] or primary is None:
                                primary = rel_path
                except Exception:
                    pass
                
    if not primary and candidates:
        primary = candidates[0]
    elif not primary and all_tex:
        primary = all_tex[0]
        
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
