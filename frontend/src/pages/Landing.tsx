import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, ShieldCheck, Lock } from 'lucide-react';
import { APP_NAME } from '../constants';

interface LandingProps {
  navigateTo: (path: string) => void;
}

export const Landing: React.FC<LandingProps> = ({ navigateTo }) => {
  const [hoveredPanel, setHoveredPanel] = useState<'voter' | 'admin' | null>(null);
  const [electionInfo, setElectionInfo] = useState<{
    title: string;
    status: string;
    formatted_window?: string;
    count: number;
  } | null>(null);

  useEffect(() => {
    fetch('/api/public/elections')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const list = data?.elections || [];
        if (list.length > 0) {
          const active = list.find((e: any) => e.registration_open || e.is_open) || list[0];
          setElectionInfo({
            title: list.length > 1 ? `${active.title} (+${list.length - 1} more)` : active.title,
            status: active.status || 'REGISTRATION',
            formatted_window: active.scheduled_window || 'Dates to be announced',
            count: list.length,
          });
        } else {
          setElectionInfo(null);
        }
      })
      .catch(() => {
        setElectionInfo(null);
      });
  }, []);

  return (
    <div className="min-h-screen w-full flex flex-col justify-between bg-paper select-none">
      {/* Top Quiet Brand Indicator */}
      <header className="w-full px-6 py-5 border-b border-line flex items-center justify-between z-10 bg-paper">
        <div className="flex items-center gap-3">
          <span className="font-display font-semibold text-xl tracking-tight text-ink">
            {APP_NAME}
          </span>
          <span className="text-xs text-text-muted border-l border-line pl-3 hidden sm:inline">
            Cryptographic Civic Voting
          </span>
        </div>
      </header>

      {/* Main Split Viewport */}
      <div className="flex-1 w-full grid grid-cols-1 md:grid-cols-2 overflow-hidden">
        {/* Left Half: Voter (Paper Theme) */}
        <motion.div
          onMouseEnter={() => setHoveredPanel('voter')}
          onMouseLeave={() => setHoveredPanel(null)}
          onClick={() => navigateTo('/user/login')}
          className={`cursor-pointer p-8 sm:p-14 lg:p-20 flex flex-col justify-between bg-paper border-b md:border-b-0 md:border-r border-line transition-all duration-300 ${
            hoveredPanel === 'admin' ? 'md:opacity-75' : 'opacity-100'
          }`}
          whileHover={{ scale: 1.002 }}
        >
          <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
            <ShieldCheck className="w-4 h-4 text-accent" />
            <span>Voter Portal</span>
          </div>

          <div className="my-12 md:my-auto max-w-lg">
            <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl text-ink font-semibold leading-[1.08] tracking-tight mb-6">
              Cast your ballot in confidence.
            </h2>
            <p className="text-text-muted text-base sm:text-lg leading-relaxed mb-8">
              Authenticate with your threshold credentials and facial liveness to cast a verifiable, end-to-end encrypted ballot.
            </p>

            <div className="inline-flex items-center gap-3 text-ink font-medium text-base group">
              <span className="border-b border-ink pb-0.5 group-hover:border-accent group-hover:text-accent transition">
                Enter Voter Portal
              </span>
              <ArrowRight className="w-4 h-4 text-accent transform group-hover:translate-x-1 transition" />
            </div>
          </div>

          <div className="text-xs text-text-muted">
            Registration &bull; Anonymous Token Issuance &bull; Merkle Receipt
          </div>
        </motion.div>

        {/* Right Half: Administrator (Ink Theme) */}
        <motion.div
          onMouseEnter={() => setHoveredPanel('admin')}
          onMouseLeave={() => setHoveredPanel(null)}
          onClick={() => navigateTo('/admin/login')}
          className={`cursor-pointer p-8 sm:p-14 lg:p-20 flex flex-col justify-between bg-ink text-on-ink transition-all duration-300 ${
            hoveredPanel === 'voter' ? 'md:opacity-75' : 'opacity-100'
          }`}
          whileHover={{ scale: 1.002 }}
        >
          <div className="flex items-center gap-2 text-xs text-on-ink-muted uppercase tracking-wider font-mono">
            <Lock className="w-4 h-4 text-accent" />
            <span>Administrator Console</span>
          </div>

          <div className="my-12 md:my-auto max-w-lg">
            <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl text-on-ink font-semibold leading-[1.08] tracking-tight mb-6">
              Oversee the election lifecycle.
            </h2>
            <p className="text-on-ink-muted text-base sm:text-lg leading-relaxed mb-8">
              Configure voting schedules, authorize ballot box opening, supervise trustee threshold ceremonies, and audit transmission outbox.
            </p>

            <div className="inline-flex items-center gap-3 text-on-ink font-medium text-base group">
              <span className="border-b border-on-ink pb-0.5 group-hover:border-accent group-hover:text-accent transition">
                Access Admin Console
              </span>
              <ArrowRight className="w-4 h-4 text-accent transform group-hover:translate-x-1 transition" />
            </div>
          </div>

          <div className="text-xs text-on-ink-muted">
            Authorized Election Officials &bull; Threshold Trustees &bull; Role Protected
          </div>
        </motion.div>
      </div>

      {/* Bottom Quiet Plain Text Status Bar */}
      <footer className="w-full px-6 py-4 border-t border-line bg-paper text-xs text-text-muted flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-ink">
            {electionInfo ? electionInfo.title : 'No election configured yet'}
          </span>
          {electionInfo && (
            <>
              <span>&bull;</span>
              <span className="font-mono uppercase text-[11px] text-text-muted">
                Status: {electionInfo.status}
              </span>
              <span>&bull;</span>
              <span className="text-text-muted">
                {electionInfo.formatted_window}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          <span>{APP_NAME} Cryptographic Protocol &bull; Zero Plaintext Ballots</span>
        </div>
      </footer>
    </div>
  );
};
