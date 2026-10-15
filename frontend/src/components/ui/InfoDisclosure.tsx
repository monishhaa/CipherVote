import React, { useState } from 'react';

export interface InfoDisclosureProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const InfoDisclosure: React.FC<InfoDisclosureProps> = ({
  title,
  defaultOpen = false,
  children,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`border border-border rounded bg-surface overflow-hidden ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 text-left flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text hover:bg-[#FAF8F5] transition-colors focus:outline-none focus:ring-1 focus:ring-primary"
      >
        <span>{title}</span>
        <svg
          className={`w-4 h-4 text-text-muted transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-1 text-xs text-text border-t border-border/60 bg-[#FDFBF7]">
          {children}
        </div>
      )}
    </div>
  );
};
