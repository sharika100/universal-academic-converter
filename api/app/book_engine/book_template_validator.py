import os
import re
from typing import Dict, Any, List
from app.models.udm import UniversalDocumentModel
from app.book_engine.book_template_analyzer import BookTemplateSpecification

class BookTemplateValidator:
    @staticmethod
    def validate_book_output(
        main_tex_content: str,
        udm: UniversalDocumentModel,
        spec: BookTemplateSpecification,
        output_dir: str
    ) -> Dict[str, Any]:
        results = {
            "overall_passed": True,
            "checks": [],
            "warnings": [],
            "sample_content_leaked": False
        }

        for sample_t in spec.sample_title_strings:
            if sample_t.lower() in main_tex_content.lower() and sample_t.lower() not in (udm.metadata.title or "").lower():
                results["checks"].append(f"[FAIL] Sample template title leaked into output: '{sample_t}'")
                results["sample_content_leaked"] = True
                results["overall_passed"] = False

        for sample_a in spec.sample_author_strings:
            if sample_a.lower() in main_tex_content.lower() and not any(sample_a.lower() in a.name.lower() for a in udm.metadata.authors):
                results["checks"].append(f"[FAIL] Sample template author leaked into output: '{sample_a}'")
                results["sample_content_leaked"] = True
                results["overall_passed"] = False

        if udm.metadata.authors:
            for a in udm.metadata.authors:
                if a.name and a.name.lower() in main_tex_content.lower():
                    results["checks"].append(f"[PASS] Source author '{a.name}' present in generated book.")
                else:
                    results["warnings"].append(f"Source author '{a.name}' not explicitly found in generated LaTeX string.")

        chap_count = len(re.findall(r'\\chapter\{', main_tex_content))
        results["checks"].append(f"[PASS] Generated {chap_count} \\chapter{{...}} blocks in main.tex.")

        referenced_imgs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', main_tex_content)
        missing_imgs = []
        for ref_img in referenced_imgs:
            clean_img = ref_img.strip()
            candidates = [
                os.path.normpath(os.path.join(output_dir, clean_img)),
                os.path.normpath(os.path.join(output_dir, "figures", os.path.basename(clean_img)))
            ]
            if not any(os.path.exists(c) or any(os.path.exists(c + ext) for ext in [".png", ".jpg", ".jpeg", ".pdf", ".eps"]) for c in candidates):
                missing_imgs.append(clean_img)

        if missing_imgs:
            results["checks"].append(f"[FAIL] Missing image files in output: {missing_imgs}")
            results["overall_passed"] = False
        else:
            results["checks"].append("[PASS] All figure image files exist in output directory.")

        return results
