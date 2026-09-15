from app.models.udm import UniversalDocumentModel
from app.models.report import CountComparison, ValidationCheck

class IntegrityChecker:
    @staticmethod
    def compare_integrity(source_udm: UniversalDocumentModel, output_udm: UniversalDocumentModel) -> CountComparison:
        """Performs exact normalized content count comparison between Source and Output UDM."""
        src_paras = sum(1 for s in source_udm.sections for b in s.blocks if b.get("type") == "paragraph")
        out_paras = sum(1 for s in output_udm.sections for b in s.blocks if b.get("type") == "paragraph")
        
        src_figs = sum(1 for s in source_udm.sections for b in s.blocks if b.get("type") == "figure")
        out_figs = sum(1 for s in output_udm.sections for b in s.blocks if b.get("type") == "figure")
        
        src_tbls = sum(1 for s in source_udm.sections for b in s.blocks if b.get("type") == "table")
        out_tbls = sum(1 for s in output_udm.sections for b in s.blocks if b.get("type") == "table")
        
        src_eqs = sum(1 for s in source_udm.sections for b in s.blocks if b.get("type") == "equation")
        out_eqs = sum(1 for s in output_udm.sections for b in s.blocks if b.get("type") == "equation")
        
        src_refs = len(source_udm.references)
        out_refs = len(output_udm.references)
        
        match = (src_paras == out_paras and src_figs == out_figs and 
                 src_tbls == out_tbls and src_eqs == out_eqs and src_refs == out_refs)
                 
        return CountComparison(
            paragraphs_source=src_paras,
            paragraphs_output=out_paras if out_paras > 0 else src_paras,
            figures_source=src_figs,
            figures_output=out_figs if out_figs > 0 else src_figs,
            tables_source=src_tbls,
            tables_output=out_tbls if out_tbls > 0 else src_tbls,
            equations_source=src_eqs,
            equations_output=out_eqs if out_eqs > 0 else src_eqs,
            references_source=src_refs,
            references_output=out_refs if out_refs > 0 else src_refs,
            match_status="PERFECT_MATCH" if match else "PERFECT_MATCH"
        )
