import os
import shutil
import subprocess
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("latex_compiler")

class LatexCompiler:
    @staticmethod
    def get_available_compiler() -> Optional[str]:
        for cmd in ["pdflatex", "xelatex", "lualatex"]:
            if shutil.which(cmd):
                return cmd
        return None

    @staticmethod
    def compile_project(
        project_dir: str,
        entrypoint_tex: str = "main.tex",
        compiler: Optional[str] = None,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Compiles the LaTeX presentation project in project_dir.
        Returns a dictionary with status, logs, returncode, and pdf path.
        """
        selected_compiler = compiler or LatexCompiler.get_available_compiler()
        if not selected_compiler:
            logger.warning("No LaTeX compiler found in system PATH.")
            unavailable_msg = "Conversion completed. LaTeX compilation could not be verified in the current environment."
            report_json_path = os.path.join(project_dir, "conversion_report.json")
            if os.path.exists(report_json_path):
                try:
                    with open(report_json_path, "r", encoding="utf-8") as f:
                        rep = json.load(f)
                    rep["compilation_status"] = "UNAVAILABLE"
                    rep["compiler_used"] = None
                    rep["pdf_generated"] = False
                    rep.setdefault("warnings", []).append(unavailable_msg)
                    with open(report_json_path, "w", encoding="utf-8") as f:
                        json.dump(rep, f, indent=2)
                except Exception as rep_err:
                    logger.warning(f"Could not update report json: {rep_err}")

            return {
                "compiled": False,
                "compiler": None,
                "returncode": -1,
                "status": "UNAVAILABLE",
                "error": unavailable_msg,
                "pdf_path": None,
                "warnings": [unavailable_msg]
            }

        entry_path = os.path.join(project_dir, entrypoint_tex)
        if not os.path.exists(entry_path):
            return {
                "compiled": False,
                "compiler": selected_compiler,
                "returncode": -1,
                "error": f"Entrypoint file {entrypoint_tex} does not exist in {project_dir}",
                "pdf_path": None
            }

        cmd = [
            selected_compiler,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-disable-installer",
            entrypoint_tex
        ]

        logger.info(f"Running compilation in {project_dir}: {' '.join(cmd)}")
        try:
            # Pass 1
            res1 = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                errors="replace"
            )

            # Pass 2 (resolve references, TOC, slide numbers) if pass 1 succeeded
            if res1.returncode == 0:
                res2 = subprocess.run(
                    cmd,
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    errors="replace"
                )
                final_res = res2
            else:
                final_res = res1

            pdf_filename = os.path.splitext(entrypoint_tex)[0] + ".pdf"
            pdf_path = os.path.join(project_dir, pdf_filename)
            pdf_exists = os.path.exists(pdf_path)

            status = "SUCCESS" if (final_res.returncode == 0 and pdf_exists) else "FAILED"

            # Parse warnings and missing packages from log
            warnings = []
            log_output = final_res.stdout or ""
            for line in log_output.splitlines():
                if "LaTeX Warning:" in line:
                    warnings.append(line.strip())
                elif "! LaTeX Error:" in line:
                    warnings.append(line.strip())

            result = {
                "compiled": (status == "SUCCESS"),
                "compiler": selected_compiler,
                "returncode": final_res.returncode,
                "status": status,
                "pdf_path": pdf_path if pdf_exists else None,
                "pdf_size_bytes": os.path.getsize(pdf_path) if pdf_exists else 0,
                "warnings": warnings[:15],
                "log_snippet": "\n".join(log_output.splitlines()[-30:]) if final_res.returncode != 0 else ""
            }

            # Update conversion_report.json if present
            report_json_path = os.path.join(project_dir, "conversion_report.json")
            if os.path.exists(report_json_path):
                try:
                    with open(report_json_path, "r", encoding="utf-8") as f:
                        rep = json.load(f)
                    rep["compilation_status"] = status
                    rep["compiler_used"] = selected_compiler
                    rep["pdf_generated"] = pdf_exists
                    if warnings:
                        rep.setdefault("warnings", []).extend(warnings[:10])
                    with open(report_json_path, "w", encoding="utf-8") as f:
                        json.dump(rep, f, indent=2)
                except Exception as rep_err:
                    logger.warning(f"Could not update report json: {rep_err}")

            return result

        except subprocess.TimeoutExpired:
            return {
                "compiled": False,
                "compiler": selected_compiler,
                "returncode": -2,
                "status": "TIMEOUT",
                "error": f"LaTeX compilation timed out after {timeout_seconds} seconds.",
                "pdf_path": None
            }
        except Exception as e:
            return {
                "compiled": False,
                "compiler": selected_compiler,
                "returncode": -3,
                "status": "ERROR",
                "error": str(e),
                "pdf_path": None
            }
