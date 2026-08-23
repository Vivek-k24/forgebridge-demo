import {useEffect, useRef, useState} from 'react';
import {Check, ChevronDown} from 'lucide-react';

export interface PartGraphSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
  secondary?: string;
}

interface PartGraphSelectProps {
  label: string;
  value: string;
  options: PartGraphSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function PartGraphSelect({
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder = 'Choose…',
  className = '',
}: PartGraphSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((option) => option.value === value);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', close);
    window.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('mousedown', close);
      window.removeEventListener('keydown', key);
    };
  }, [open]);

  return (
    <div className={`pg2-select ${className}`} ref={rootRef}>
      <span className="pg2-select-label">{label}</span>
      <button
        type="button"
        className={`pg2-select-trigger ${open ? 'open' : ''}`}
        onClick={() => !disabled && setOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
      >
        <span className={!selected ? 'placeholder' : ''}>{selected?.label ?? placeholder}</span>
        <ChevronDown size={15} />
      </button>
      {open ? (
        <div className="pg2-select-menu" role="listbox" aria-label={label}>
          <div className="pg2-select-scroll">
            {options.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.value === value}
                key={option.value}
                disabled={option.disabled}
                className={option.value === value ? 'selected' : ''}
                onClick={() => {
                  if (option.disabled) return;
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                <span>
                  <strong>{option.label}</strong>
                  {option.secondary ? <small>{option.secondary}</small> : null}
                </span>
                {option.value === value ? <Check size={14} /> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
