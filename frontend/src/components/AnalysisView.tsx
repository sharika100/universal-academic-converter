import React from 'react';
import { Check, AlertTriangle, Cpu, Gauge, Zap } from 'lucide-react';

interface UdmData {
  metadata: {
    title: string;
    authors: any[];
    affiliations: any[];
    abstract: string;
    keywords: string[];
  };
  sections: any[];
  references: any[];
  parsing_confidence: number;
  warnings: string[];
}

interface SpecData {
  format_type: string;
  document_class: string;
  author_style: string;
  citation_system: string;
  template_confidence: number;
  detected_rules: string[];
  warnings: string[];
}

interface MappingData {
  compatibility: {
    content_mapping: number;
    figures: number;
    tables: number;
    equations: number;
    references: number;
    overall: number;
  };
  paragraphs_source: number;
  figures_source: number;
  tables_source: number;
  equations_source: number;
  references_source: number;
  warnings: string[];
}

interface AnalysisViewProps {
  sourceUdm: UdmData | null;
  destSpec: SpecData | null;
  mapping: MappingData | null;
}

export const AnalysisView: React.FC<AnalysisViewProps> = ({ sourceUdm, destSpec, mapping }) => {
  if (!sourceUdm || !destSpec) return null;

  const totalParas = sourceUdm.sections.reduce((acc, s) => acc + (s.blocks ? s.blocks.filter((b: any) => b.type === 'paragraph').length : 0), 0);
  const totalFigs = sourceUdm.sections.reduce((acc, s) => acc + (s.blocks ? s.blocks.filter((b: any) => b.type === 'figure').length : 0), 0);
  const totalTbls = sourceUdm.sections.reduce((acc, s) => acc + (s.blocks ? s.blocks.filter((b: any) => b.type === 'table').length : 0), 0);
  const totalEqs = sourceUdm.sections.reduce((acc, s) => acc + (s.blocks ? s.blocks.filter((b: any) => b.type === 'equation').length : 0), 0);

  return (
    <div style={{ marginTop: '32px' }}>
      <div className="analysis-grid">
        {/* Source Analysis Card */}
        <div className="analysis-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu color="#6366F1" size={18} /> Source Document Analysis
            </h3>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#A5B4FC' }}>
              Confidence: {sourceUdm.parsing_confidence}%
            </span>
          </div>

          <div className="stat-row">
            <span className="stat-label">Title</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.metadata.title ? 'Detected' : 'Missing'}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Authors</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.metadata.authors.length} author(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Affiliations</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.metadata.affiliations.length} detected</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Abstract</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.metadata.abstract ? 'Detected' : 'None'}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Keywords</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.metadata.keywords.length} keyword(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Sections</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.sections.length} section(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Paragraphs</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {totalParas}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Figures</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {totalFigs} figure(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Tables</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {totalTbls} table(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Equations</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {totalEqs} equation(s)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">References</span>
            <span className="stat-value"><Check size={14} color="#10B981" /> {sourceUdm.references.length} reference(s)</span>
          </div>

          <div className="confidence-gauge">
            <div className="confidence-fill" style={{ width: `${sourceUdm.parsing_confidence}%` }}></div>
          </div>
        </div>

        {/* Destination Template Analysis Card */}
        <div className="analysis-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Gauge color="#10B981" size={18} /> Destination Template Analysis
            </h3>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#34D399' }}>
              Confidence: {destSpec.template_confidence}%
            </span>
          </div>

          <div className="stat-row">
            <span className="stat-label">Format Type</span>
            <span className="stat-value">{destSpec.format_type.toUpperCase()}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Document Class</span>
            <span className="stat-value">{destSpec.document_class}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Author Formatting</span>
            <span className="stat-value">{destSpec.author_style.toUpperCase()}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Citation System</span>
            <span className="stat-value">{destSpec.citation_system}</span>
          </div>

          <div style={{ marginTop: '16px', fontSize: '0.85rem', color: '#94A3B8' }}>
            <strong>DETECTED TEMPLATE RULES:</strong>
            <ul style={{ paddingLeft: '18px', marginTop: '6px', lineHeight: '1.6' }}>
              {destSpec.detected_rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ul>
          </div>

          <div className="confidence-gauge">
            <div className="confidence-fill" style={{ width: `${destSpec.template_confidence}%`, background: '#10B981' }}></div>
          </div>
        </div>
      </div>

      {/* Compatibility Matrix Breakdown */}
      {mapping && (
        <div className="analysis-card" style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap color="#F59E0B" size={18} /> Universal Document Model Compatibility Estimate
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', textAlign: 'center' }}>
            <div style={{ background: '#0B0F19', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Content Mapping</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#A5B4FC' }}>{mapping.compatibility.content_mapping}%</div>
            </div>
            <div style={{ background: '#0B0F19', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Figures</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34D399' }}>{mapping.compatibility.figures}%</div>
            </div>
            <div style={{ background: '#0B0F19', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Tables</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#FBBF24' }}>{mapping.compatibility.tables}%</div>
            </div>
            <div style={{ background: '#0B0F19', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Equations</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34D399' }}>{mapping.compatibility.equations}%</div>
            </div>
            <div style={{ background: '#0B0F19', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>References</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#A5B4FC' }}>{mapping.compatibility.references}%</div>
            </div>
            <div style={{ background: 'rgba(99, 102, 241, 0.2)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
              <div style={{ fontSize: '0.75rem', color: '#A5B4FC', fontWeight: 600 }}>OVERALL COMPATIBILITY</div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#FFFFFF' }}>{mapping.compatibility.overall}%</div>
            </div>
          </div>

          {mapping.warnings.length > 0 && (
            <div className="warning-box">
              <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <AlertTriangle size={15} /> Document Compiler Warnings & Mappings:
              </div>
              {mapping.warnings.map((w, idx) => (
                <div key={idx}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
