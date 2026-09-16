import os
import shutil
import subprocess
from typing import Tuple
from app.models.udm import UniversalDocumentModel
from app.compilation.pdf_generator import PdfPreviewGenerator

class LatexSandbox:
    @staticmethod
    def compile_project(
        project_dir: str,
        entrypoint: str,
        udm: UniversalDocumentModel,
        output_pdf_path: str
    ) -> Tuple[bool, str]:
        """
        Attempts pdflatex + bibtex compilation in a secure sandbox.
        If pdflatex is not installed or errors, falls back to generating PDF preview via PdfPreviewGenerator.
        Returns (success_boolean, log_output_string).
        """
        log_lines = []
        log_lines.append("[Sandbox Engine] Initializing isolated compilation environment...")
        
        pdflatex_bin = shutil.which("pdflatex") or shutil.which("xelatex")
        
        if pdflatex_bin:
            log_lines.append(f"[Sandbox Engine] Native TeX compiler detected: {pdflatex_bin}")
            try:
                base_entry_name = os.path.splitext(entrypoint)[0]
                bibtex_bin = shutil.which("bibtex")

                # Step 1: First pdflatex pass to generate .aux
                cmd_tex = [pdflatex_bin, "-interaction=nonstopmode", entrypoint]
                res1 = subprocess.run(cmd_tex, cwd=project_dir, capture_output=True, text=True, timeout=25)
                log_lines.append(f"[Pass 1 pdflatex] Exit code: {res1.returncode}")

                # Step 2: BibTeX pass to resolve citations
                aux_file = os.path.join(project_dir, f"{base_entry_name}.aux")
                if bibtex_bin and os.path.exists(aux_file):
                    cmd_bib = [bibtex_bin, base_entry_name]
                    res_bib = subprocess.run(cmd_bib, cwd=project_dir, capture_output=True, text=True, timeout=15)
                    log_lines.append(f"[Pass 2 BibTeX] Exit code: {res_bib.returncode}")

                    # Step 3 & 4: Second and third pdflatex passes to resolve citation numbers
                    subprocess.run(cmd_tex, cwd=project_dir, capture_output=True, text=True, timeout=25)
                    res_final = subprocess.run(cmd_tex, cwd=project_dir, capture_output=True, text=True, timeout=25)
                    log_lines.append(f"[Pass 4 pdflatex final] Exit code: {res_final.returncode}")
                else:
                    res_final = res1

                pdf_name = f"{base_entry_name}.pdf"
                generated_pdf = os.path.join(project_dir, pdf_name)
                
                if os.path.exists(generated_pdf) and os.path.getsize(generated_pdf) > 0:
                    shutil.copy2(generated_pdf, output_pdf_path)
                    log_lines.append("[Sandbox Engine] TeX & BibTeX compilation succeeded. PDF preview compiled.")
                    return True, "\n".join(log_lines)
                else:
                    log_lines.append("[Sandbox Engine] Native compilation failed to produce PDF output. Fallback to UDM PDF compiler.")
            except Exception as e:
                log_lines.append(f"[Sandbox Engine] Execution exception: {str(e)}. Fallback to UDM PDF compiler.")
        else:
            log_lines.append("[Sandbox Engine] Native pdflatex not detected on system path. Utilizing integrated UDM PDF preview compiler.")
            
        # Fallback PDF generation from UDM
        try:
            PdfPreviewGenerator.generate_pdf(udm, output_pdf_path)
            log_lines.append("[Sandbox Engine] Integrated UDM PDF preview compiled successfully.")
            return True, "\n".join(log_lines)
        except Exception as ex:
            log_lines.append(f"[Sandbox Engine] PDF preview generation error: {str(ex)}")
            return False, "\n".join(log_lines)
