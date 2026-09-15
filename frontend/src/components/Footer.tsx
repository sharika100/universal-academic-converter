import React from 'react';
import { Heart, GraduationCap } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer style={{
      marginTop: '48px',
      padding: '24px 16px',
      borderTop: '1px solid #1F2937',
      textAlign: 'center',
      color: '#94A3B8',
      fontSize: '0.9rem'
    }}>
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        background: 'rgba(17, 24, 39, 0.8)',
        border: '1px solid #374151',
        padding: '10px 20px',
        borderRadius: '30px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
      }}>
        <GraduationCap color="#6366F1" size={18} />
        <span>Built by <strong style={{ color: '#F8FAFC' }}>Sharika T R</strong>, Assistant Professor, Department of CSE, ASIET</span>
      </div>
    </footer>
  );
};
