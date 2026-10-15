import React from 'react';
import { APP_NAME } from '../constants';

interface NavbarProps {
  currentPath: string;
  navigateTo: (path: string) => void;
  electionStatus?: string;
  isOpen?: boolean;
  electionId?: string;
  electionList?: Array<{ election_id: string; title: string; status: string; is_open: boolean }>;
  onSelectElection?: (electionId: string) => void;
  isAdmin: boolean;
  isAdminPath: boolean;
  onAdminLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentPath,
  navigateTo,
  isAdmin,
  isAdminPath,
}) => {
  // If inside Admin Console (/admin*), AdminConsole renders its own complete dark-navy sidebar layout
  if (isAdminPath && isAdmin) {
    return null;
  }

  return (
    <header className="bg-surface border-b border-border sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Brand / Logo */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigateTo('/')}
              className="flex items-center gap-2 text-left group focus:outline-none"
            >
              <div className="w-7 h-7 bg-primary text-white rounded flex items-center justify-center font-serif font-bold text-sm">
                C
              </div>
              <div>
                <span className="font-serif font-semibold text-base text-text tracking-tight group-hover:text-primary transition">
                  {APP_NAME}
                </span>
                <span className="hidden sm:inline-block text-[11px] text-text-muted ml-2 font-normal">
                  Institutional Cryptographic Voting
                </span>
              </div>
            </button>
          </div>

          {/* Navigation Links per role */}
          <nav className="flex items-center gap-1 sm:gap-2 text-xs font-medium">
            <button
              type="button"
              onClick={() => navigateTo('/vote')}
              className={`px-2.5 py-1.5 rounded transition ${
                currentPath === '/vote' || currentPath === '/register'
                  ? 'bg-primary text-white font-semibold'
                  : 'text-text-muted hover:text-text hover:bg-black/5'
              }`}
            >
              Voter Portal
            </button>

            <button
              type="button"
              onClick={() => navigateTo('/audit')}
              className={`px-2.5 py-1.5 rounded transition ${
                currentPath === '/audit' || currentPath === '/auditor'
                  ? 'bg-primary text-white font-semibold'
                  : 'text-text-muted hover:text-text hover:bg-black/5'
              }`}
            >
              Public Audit
            </button>

            <button
              type="button"
              onClick={() => navigateTo('/trustee')}
              className={`px-2.5 py-1.5 rounded transition ${
                currentPath === '/trustee'
                  ? 'bg-primary text-white font-semibold'
                  : 'text-text-muted hover:text-text hover:bg-black/5'
              }`}
            >
              Trustees
            </button>

            <span className="text-border mx-1">|</span>

            <button
              type="button"
              onClick={() => navigateTo('/admin')}
              className={`px-2.5 py-1.5 rounded transition ${
                isAdminPath
                  ? 'bg-primary text-white font-semibold'
                  : 'text-text-muted hover:text-text hover:bg-black/5'
              }`}
            >
              Admin Access
            </button>
          </nav>
        </div>
      </div>
    </header>
  );
};
