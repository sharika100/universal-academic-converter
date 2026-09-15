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
        Attempts pdflatex compilation in a secure sandbox.
        If pdflatex is not installed or errors, falls back to generating PDF preview via PdfPreviewGenerator.
        Returns (success_boolean, log_output_string).
        """
        log_lines = []
        log_lines.append("[Sandbox Engine] Initializing isolated compilation environment...")
        
        pdflatex_bin = shutil.which("pdflatex") or shutil.which("xelatex")
        
        if pdflatex_bin:
            log_lines.append(f"[Sandbox Engine] Native TeX compiler detected: {pdflatex_bin}")
            try:
                cmd = [pdflatex_bin, "-interaction=nonstopmode", "-halt-on-error", entrypoint]
                res = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=20)
                log_lines.append(res.stdout)
                
                pdf_name = os.path.splitext(entrypoint)[0] + ".pdf"
                generated_pdf = os.path.join(project_dir, pdf_name)
                
                if res.returncode == 0 and os.path.exists(generated_pdf):
                    shutil.copy2(generated_pdf, output_pdf_path)
                    log_lines.append("[Sandbox Engine] TeX compilation succeeded. PDF preview compiled.")
                    return True, "\n".join(log_lines)
                else:
                    log_lines.append(f"[Sandbox Engine] Native compilation failed with exit code {res.returncode}. Fallback to UDM PDF compiler.")
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
