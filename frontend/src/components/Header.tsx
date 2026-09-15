import React from 'react';
import { Sparkles } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="app-header">
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', background: 'rgba(99, 102, 241, 0.12)', borderRadius: '20px', border: '1px solid rgba(99, 102, 241, 0.25)', color: '#A5B4FC', fontSize: '0.85rem', fontWeight: 500, marginBottom: '16px' }}>
        <Sparkles size={16} /> Universal Document Model Compiler Architecture
      </div>
      <h1>Universal Academic Format Converter</h1>
      <p>Convert your manuscript to a different journal, conference, publisher, or book template.</p>
    </header>
  );
};
