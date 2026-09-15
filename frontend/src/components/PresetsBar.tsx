import React from 'react';
import { Layers, ArrowRight } from 'lucide-react';

interface Preset {
  id: string;
  name: string;
  source_type: string;
  dest_type: string;
  description: string;
}

interface PresetsBarProps {
  presets: Preset[];
  onSelectPreset: (preset: Preset) => void;
  selectedPresetId?: string;
}

export const PresetsBar: React.FC<PresetsBarProps> = ({ presets, onSelectPreset, selectedPresetId }) => {
  return (
    <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '12px', padding: '16px 20px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '12px' }}>
        <Layers size={18} color="#6366F1" /> Quick Presets & Test Packages:
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        {presets.map((p) => {
          const isSelected = selectedPresetId === p.id;
          return (
            <button
              key={p.id}
              onClick={() => onSelectPreset(p)}
              style={{
                background: isSelected ? 'rgba(99, 102, 241, 0.15)' : '#1F2937',
                border: isSelected ? '1px solid #6366F1' : '1px solid #374151',
                borderRadius: '8px',
                padding: '12px 14px',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: isSelected ? '#A5B4FC' : '#F8FAFC', marginBottom: '4px' }}>
                {p.name}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>{p.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
