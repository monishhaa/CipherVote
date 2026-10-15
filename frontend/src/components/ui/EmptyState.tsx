import React from 'react';

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
}) => {
  return (
    <div className="py-12 px-4 text-center border border-dashed border-border rounded-lg bg-surface/50">
      {icon && <div className="text-text-muted/70 mb-3 flex justify-center">{icon}</div>}
      <h4 className="font-serif text-base font-medium text-text">{title}</h4>
      {description && <p className="text-xs text-text-muted mt-1 max-w-sm mx-auto">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};
