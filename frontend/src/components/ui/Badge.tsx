import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'accent';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'sm',
  className = '',
  ...props
}) => {
  const variantStyles = {
    neutral: 'bg-[#EAE6DD] text-[#3D4752] border-[#D5CEBF]',
    success: 'bg-[#E2EFE7] text-[#1E4D36] border-[#B7D8C4]',
    warning: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
    danger: 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]',
    info: 'bg-[#E0F2FE] text-[#075985] border-[#BAE6FD]',
    accent: 'bg-[#F5EEDC] text-[#7A5A22] border-[#E5D7B7]',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  };

  return (
    <span
      className={`inline-flex items-center font-medium border rounded-sm tracking-wide ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};

export const StatusChip: React.FC<{ status: string; className?: string }> = ({ status, className }) => {
  const normalized = (status || '').toUpperCase();
  let variant: BadgeProps['variant'] = 'neutral';
  let label = status;

  switch (normalized) {
    case 'REGISTRATION':
    case 'REGISTRATION OPEN':
      variant = 'info';
      label = 'Registration Open';
      break;
    case 'VOTING':
    case 'VOTING OPEN':
    case 'ACTIVE':
    case 'OPEN':
      variant = 'success';
      label = 'Voting Active';
      break;
    case 'TALLYING':
    case 'DECRYPTING':
      variant = 'warning';
      label = 'Tally In Progress';
      break;
    case 'ENDED':
    case 'CLOSED':
    case 'COMPLETED':
      variant = 'neutral';
      label = 'Election Closed';
      break;
    case 'VERIFIED':
    case 'VALID':
    case 'AUTHENTICATED':
      variant = 'success';
      label = 'Verified';
      break;
    case 'REJECTED':
    case 'INVALID':
    case 'TAMPERED':
      variant = 'danger';
      label = 'Invalid';
      break;
    case 'PENDING':
      variant = 'warning';
      label = 'Pending';
      break;
    default:
      variant = 'neutral';
      label = status;
  }

  return <Badge variant={variant} className={className}>{label}</Badge>;
};
