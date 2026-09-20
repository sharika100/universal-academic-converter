import React from 'react';
import { Sparkles, FileText, BookOpen } from 'lucide-react';

interface HeaderProps {
  currentPath?: string;
  onNavigate?: (path: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ currentPath = '/', onNavigate }) => {
  const isBook = currentPath === '/book-converter';

  const handleNav = (path: string) => {
    if (onNavigate) {
      onNavigate(path);
    } else {
      window.history.pushState({}, '', path);
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };

  return (
    <header className="app-header">
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', background: 'rgba(99, 102, 241, 0.12)', borderRadius: '20px', border: '1px solid rgba(99, 102, 241, 0.25)', color: '#A5B4FC', fontSize: '0.85rem', fontWeight: 500, marginBottom: '16px' }}>
        <Sparkles size={16} /> Universal Document Model Compiler Architecture
      </div>
      <h1>Universal Academic Format Converter</h1>
      <p>Convert your manuscript to a different journal, conference, publisher, or book template.</p>

      {/* Navigation Mode Switcher */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        background: '#111827',
        border: '1px solid #1F2937',
        borderRadius: '14px',
        padding: '5px',
        marginTop: '20px',
        gap: '6px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)'
      }}>
        <button
          type="button"
          onClick={() => handleNav('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 20px',
            borderRadius: '9px',
            border: !isBook ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 600,
            background: !isBook ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
            color: !isBook ? '#F8FAFC' : '#94A3B8',
            transition: 'all 0.15s ease'
          }}
        >
          <FileText size={16} color={!isBook ? '#A5B4FC' : '#64748B'} />
          <span>Research Paper Converter</span>
        </button>

        <button
          type="button"
          onClick={() => handleNav('/book-converter')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 20px',
            borderRadius: '9px',
            border: isBook ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 600,
            background: isBook ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
            color: isBook ? '#F8FAFC' : '#94A3B8',
            transition: 'all 0.15s ease'
          }}
        >
          <BookOpen size={16} color={isBook ? '#A5B4FC' : '#64748B'} />
          <span>Book Converter</span>
          <span style={{
            fontSize: '0.68rem',
            padding: '2px 8px',
            borderRadius: '10px',
            background: isBook ? '#6366F1' : '#374151',
            color: '#FFFFFF',
            fontWeight: 700,
            letterSpacing: '0.02em'
          }}>
            Multi-Chapter
          </span>
        </button>
      </div>
    </header>
  );
};
