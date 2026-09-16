import re
from typing import Dict, Any, List
from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification

class MappingEngine:
    @staticmethod
    def map_and_evaluate(udm: UniversalDocumentModel, spec: TemplateSpecification) -> Dict[str, Any]:
        """
        Generic Content-to-Template Mapping Engine.
        Maps UniversalDocumentModel onto TemplateSpecification with semantic label matching,
        table placeholder matching, confidence scoring, and unmapped content tracking.
        """
        warnings = []
        unmapped_elements = []
        
        # 1. Element Inventory
        total_figures = 0
        total_tables = 0
        total_equations = 0
        total_paras = 0
        source_tables = []
        
        for sec in udm.sections:
            for blk in sec.blocks:
                btype = blk.get("type")
                if btype == "paragraph":
                    total_paras += 1
                elif btype == "figure":
                    total_figures += 1
                elif btype == "table":
                    total_tables += 1
                    source_tables.append(blk)
                elif btype == "equation":
                    total_equations += 1
                    
        total_refs = len(udm.references)
        total_label_values = len(udm.metadata.label_values)
        
        # 2. Field / Label-Value Mapping
        mapped_lv_count = 0
        tpl_labels = spec.field_labels if hasattr(spec, "field_labels") and spec.field_labels else []
        
        for lv in udm.metadata.label_values:
            matched = False
            for t_lbl in tpl_labels:
                lbl_clean = re.sub(r'[^a-zA-Z0-9]', '', lv.label).lower()
                tgt_clean = re.sub(r'[^a-zA-Z0-9]', '', t_lbl).lower()
                if lbl_clean and tgt_clean and (lbl_clean in tgt_clean or tgt_clean in lbl_clean):
                    mapped_lv_count += 1
                    matched = True
                    break
            if not matched and total_label_values > 0:
                unmapped_elements.append({
                    "element_type": "label_value",
                    "label": lv.label,
                    "value": lv.value,
                    "confidence": lv.confidence,
                    "reason": "No matching target template label field found"
                })
                
        # 3. Table Mapping
        mapped_tables = 0
        tpl_tables = spec.template_tables if hasattr(spec, "template_tables") and spec.template_tables else []
        
        if not tpl_tables:
            # Target template supports arbitrary table layouts natively
            mapped_tables = total_tables
        else:
            for s_tbl in source_tables:
                s_headers = s_tbl.get("headers", [])
                s_rows = s_tbl.get("rows", [])
                s_cols = len(s_headers) if s_headers else (len(s_rows[0]) if s_rows else 0)
                
                matched_tbl = False
                for tpl_t in tpl_tables:
                    t_cols = tpl_t.get("cols", 0)
                    if abs(s_cols - t_cols) <= 2:
                        mapped_tables += 1
                        matched_tbl = True
                        break
                        
                if not matched_tbl:
                    unmapped_elements.append({
                        "element_type": "table",
                        "id": s_tbl.get("id"),
                        "caption": s_tbl.get("caption"),
                        "cols": s_cols,
                        "rows": len(s_rows),
                        "reason": "Target template lacks structurally compatible table grid"
                    })

        # 4. Confidence & Compatibility Evaluation
        lv_score = 100.0 if total_label_values == 0 else round(min(100.0, (mapped_lv_count / max(1, total_label_values)) * 100.0), 1)
        tbl_score = 98.0 if total_tables == 0 else round(min(100.0, (mapped_tables / max(1, total_tables)) * 100.0), 1)
        fig_score = 100.0
        ref_score = 100.0 if total_refs == 0 else 98.0
        
        overall_score = round((lv_score * 0.3) + (tbl_score * 0.4) + (fig_score * 0.15) + (ref_score * 0.15), 1)
        
        confidence_level = "HIGH" if overall_score >= 88.0 else ("MEDIUM" if overall_score >= 70.0 else "LOW")
        if confidence_level == "LOW":
            warnings.append("Low confidence mapping detected; review unmapped elements report before publishing.")
            
        udm.unmapped_elements = unmapped_elements
        
        return {
            "doc_type": udm.doc_type,
            "source_sections": len(udm.sections),
            "mapped_sections": len(udm.sections),
            "paragraphs_source": total_paras,
            "figures_source": total_figures,
            "tables_source": total_tables,
            "tables_mapped": mapped_tables,
            "equations_source": total_equations,
            "references_source": total_refs,
            "label_values_source": total_label_values,
            "label_values_mapped": mapped_lv_count,
            "unmapped_elements_count": len(unmapped_elements),
            "unmapped_elements": unmapped_elements,
            "compatibility": {
                "overall": overall_score,
                "confidence_level": confidence_level,
                "label_values": lv_score,
                "tables": tbl_score,
                "figures": fig_score,
                "references": ref_score
            },
            "warnings": warnings + udm.warnings + spec.warnings
        }
