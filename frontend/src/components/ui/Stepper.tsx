import React from 'react';

export interface StepItem {
  id: number;
  label: string;
  description?: string;
}

export interface StepperProps {
  steps: StepItem[];
  currentStep: number; // 1-indexed
  onStepClick?: (stepId: number) => void;
  className?: string;
}

export const Stepper: React.FC<StepperProps> = ({
  steps,
  currentStep,
  onStepClick,
  className = '',
}) => {
  return (
    <nav aria-label="Progress" className={`w-full ${className}`}>
      <ol className="flex items-center justify-between gap-1 sm:gap-2">
        {steps.map((step, index) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;
          const isClickable = onStepClick && isCompleted;

          return (
            <li
              key={step.id}
              className={`flex-1 flex flex-col items-center sm:items-start relative group ${
                index !== steps.length - 1 ? 'pr-2' : ''
              }`}
            >
              {/* Top bar connector */}
              <div
                className={`w-full h-1 mb-2 rounded-full transition-colors ${
                  isCompleted
                    ? 'bg-primary'
                    : isCurrent
                    ? 'bg-accent'
                    : 'bg-[#E3DED3]'
                }`}
              />

              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onStepClick(step.id)}
                className={`text-left w-full focus:outline-none ${
                  isClickable ? 'cursor-pointer' : 'cursor-default'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-semibold transition-colors ${
                      isCompleted
                        ? 'bg-primary text-white'
                        : isCurrent
                        ? 'bg-accent text-white'
                        : 'bg-[#EAE6DD] text-text-muted'
                    }`}
                  >
                    {isCompleted ? (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      step.id
                    )}
                  </span>
                  <span
                    className={`text-xs font-medium truncate ${
                      isCurrent
                        ? 'text-text font-semibold'
                        : isCompleted
                        ? 'text-text'
                        : 'text-text-muted'
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
