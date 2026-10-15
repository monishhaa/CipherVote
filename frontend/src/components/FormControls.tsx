import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Eye, EyeOff } from 'lucide-react';

export interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helpText?: string;
  variant?: 'dark' | 'light';
}

export const FormInput: React.FC<FormInputProps> = ({
  label,
  error,
  helpText,
  variant = 'dark',
  className = '',
  disabled,
  ...props
}) => {
  const isDark = variant === 'dark';
  return (
    <div className="w-full">
      {label && (
        <label className={`block text-[11px] font-mono uppercase tracking-wider mb-1.5 ${isDark ? 'text-on-ink/80' : 'text-text-muted'}`}>
          {label}
        </label>
      )}
      <input
        disabled={disabled}
        className={`w-full px-3.5 py-2.5 rounded text-sm transition focus:outline-none ${
          isDark
            ? 'bg-ink text-white border border-ink-3 placeholder:text-on-ink/30 focus:border-on-ink disabled:bg-ink-2/60 disabled:text-on-ink/40'
            : 'bg-paper text-ink border border-line placeholder:text-text-muted/40 focus:border-ink disabled:bg-paper-2 disabled:text-text-muted/50'
        } ${error ? (isDark ? 'border-red-500 focus:border-red-400' : 'border-red-500 focus:border-red-600') : ''} ${className}`}
        {...props}
      />
      {error && <p className="text-[11px] text-red-400 mt-1 font-mono">{error}</p>}
      {helpText && !error && <p className={`text-[11px] mt-1 ${isDark ? 'text-on-ink/50' : 'text-text-muted'}`}>{helpText}</p>}
    </div>
  );
};

export interface PasswordInputProps extends Omit<FormInputProps, 'type'> {}

export const PasswordInput: React.FC<PasswordInputProps> = ({
  label,
  error,
  helpText,
  variant = 'dark',
  className = '',
  ...props
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const isDark = variant === 'dark';

  return (
    <div className="w-full">
      {label && (
        <label className={`block text-[11px] font-mono uppercase tracking-wider mb-1.5 ${isDark ? 'text-on-ink/80' : 'text-text-muted'}`}>
          {label}
        </label>
      )}
      <div className="relative">
        <input
          type={showPassword ? 'text' : 'password'}
          className={`w-full px-3.5 py-2.5 pr-10 rounded text-sm transition focus:outline-none ${
            isDark
              ? 'bg-ink text-white border border-ink-3 placeholder:text-on-ink/30 focus:border-on-ink'
              : 'bg-paper text-ink border border-line placeholder:text-text-muted/40 focus:border-ink'
          } ${error ? 'border-red-500' : ''} ${className}`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className={`absolute right-3 top-1/2 -translate-y-1/2 p-1 text-xs transition ${
            isDark ? 'text-on-ink/50 hover:text-white' : 'text-text-muted hover:text-ink'
          }`}
          title={showPassword ? 'Hide password' : 'Show password'}
        >
          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error && <p className="text-[11px] text-red-400 mt-1 font-mono">{error}</p>}
      {helpText && !error && <p className={`text-[11px] mt-1 ${isDark ? 'text-on-ink/50' : 'text-text-muted'}`}>{helpText}</p>}
    </div>
  );
};

export interface FormTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helpText?: string;
  variant?: 'dark' | 'light';
}

export const FormTextarea: React.FC<FormTextareaProps> = ({
  label,
  error,
  helpText,
  variant = 'dark',
  className = '',
  disabled,
  ...props
}) => {
  const isDark = variant === 'dark';
  return (
    <div className="w-full">
      {label && (
        <label className={`block text-[11px] font-mono uppercase tracking-wider mb-1.5 ${isDark ? 'text-on-ink/80' : 'text-text-muted'}`}>
          {label}
        </label>
      )}
      <textarea
        disabled={disabled}
        className={`w-full px-3.5 py-2.5 rounded text-sm transition focus:outline-none resize-y ${
          isDark
            ? 'bg-ink text-white border border-ink-3 placeholder:text-on-ink/30 focus:border-on-ink disabled:bg-ink-2/60 disabled:text-on-ink/40'
            : 'bg-paper text-ink border border-line placeholder:text-text-muted/40 focus:border-ink disabled:bg-paper-2 disabled:text-text-muted/50'
        } ${error ? 'border-red-500' : ''} ${className}`}
        {...props}
      />
      {error && <p className="text-[11px] text-red-400 mt-1 font-mono">{error}</p>}
      {helpText && !error && <p className={`text-[11px] mt-1 ${isDark ? 'text-on-ink/50' : 'text-text-muted'}`}>{helpText}</p>}
    </div>
  );
};

export interface CustomSelectOption {
  value: string | number;
  label: string;
  description?: string;
  badge?: string;
}

export interface CustomSelectProps {
  label?: string;
  options: CustomSelectOption[];
  value: string | number;
  onChange: (val: any) => void;
  disabled?: boolean;
  placeholder?: string;
  variant?: 'dark' | 'light';
  className?: string;
  searchable?: boolean;
}

export const CustomSelect: React.FC<CustomSelectProps> = ({
  label,
  options,
  value,
  onChange,
  disabled = false,
  placeholder = 'Select option...',
  variant = 'dark',
  className = '',
  searchable = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const isDark = variant === 'dark';

  const selectedOption = options.find((o) => String(o.value) === String(value));

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOptions = searchable && search
    ? options.filter((o) =>
        o.label.toLowerCase().includes(search.toLowerCase()) ||
        (o.description && o.description.toLowerCase().includes(search.toLowerCase()))
      )
    : options;

  return (
    <div className={`w-full relative ${className}`} ref={containerRef}>
      {label && (
        <label className={`block text-[11px] font-mono uppercase tracking-wider mb-1.5 ${isDark ? 'text-on-ink/80' : 'text-text-muted'}`}>
          {label}
        </label>
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`w-full px-3.5 py-2.5 rounded text-sm text-left flex items-center justify-between transition focus:outline-none ${
          isDark
            ? 'bg-ink text-white border border-ink-3 hover:border-on-ink/50 focus:border-on-ink disabled:bg-ink-2/60 disabled:text-on-ink/40'
            : 'bg-paper text-ink border border-line hover:border-ink/50 focus:border-ink disabled:bg-paper-2 disabled:text-text-muted/50'
        }`}
      >
        <div className="flex items-center gap-2 truncate pr-2">
          {selectedOption ? (
            <>
              <span className="font-medium text-white truncate">{selectedOption.label}</span>
              {selectedOption.badge && (
                <span className="text-[10px] font-mono bg-ink-3 text-on-ink/80 px-1.5 py-0.5 rounded border border-ink-3">
                  {selectedOption.badge}
                </span>
              )}
            </>
          ) : (
            <span className={isDark ? 'text-on-ink/40' : 'text-text-muted/40'}>{placeholder}</span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''} ${isDark ? 'text-on-ink/60' : 'text-text-muted'}`} />
      </button>

      {isOpen && (
        <div
          className={`absolute left-0 right-0 top-full mt-1.5 z-50 rounded-lg shadow-2xl border max-h-60 overflow-y-auto ${
            isDark ? 'bg-ink-2 border-ink-3 text-white' : 'bg-paper border-line text-ink'
          }`}
        >
          {searchable && (
            <div className="p-2 border-b border-ink-3">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                autoFocus
                className="w-full px-2.5 py-1.5 bg-ink text-white text-xs rounded border border-ink-3 focus:outline-none"
              />
            </div>
          )}
          <div className="py-1">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-on-ink/40">No options found</div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = String(opt.value) === String(value);
                return (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => {
                      onChange(opt.value);
                      setIsOpen(false);
                      setSearch('');
                    }}
                    className={`w-full px-3 py-2 text-xs flex items-center justify-between text-left transition ${
                      isSelected
                        ? (isDark ? 'bg-ink-3 text-white font-semibold' : 'bg-paper-2 text-ink font-semibold')
                        : (isDark ? 'text-on-ink/90 hover:bg-ink/60' : 'text-text hover:bg-paper-2/60')
                    }`}
                  >
                    <div>
                      <div className="font-medium">{opt.label}</div>
                      {opt.description && (
                        <div className={`text-[10px] mt-0.5 ${isDark ? 'text-on-ink/50' : 'text-text-muted'}`}>
                          {opt.description}
                        </div>
                      )}
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-accent flex-shrink-0 ml-2" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
