import os
import zipfile
import shutil
from typing import List, Tuple

class ZipGuard:
    @staticmethod
    def inspect_and_extract_safe(zip_path: str, extract_dir: str) -> Tuple[List[str], List[str]]:
        """
        Safely extracts a ZIP archive into extract_dir with Path Traversal protection.
        Returns (list_of_relative_files, list_of_warnings).
        """
        file_tree = []
        warnings = []
        
        os.makedirs(extract_dir, exist_ok=True)
        abs_target_dir = os.path.abspath(extract_dir)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                # Security check for Path Traversal (Zip Slip)
                filename = member.filename
                if filename.startswith('/') or filename.startswith('\\') or '..' in filename:
                    warnings.append(f"Skipped unsafe path entry: {filename}")
                    continue
                
                target_path = os.path.abspath(os.path.join(abs_target_dir, filename))
                if not target_path.startswith(abs_target_dir):
                    warnings.append(f"Blocked Zip Slip path traversal attempt: {filename}")
                    continue
                
                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    file_tree.append(filename.replace('\\', '/'))
                    
        return file_tree, warnings
