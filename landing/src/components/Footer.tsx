import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="mx-auto mt-28 max-w-[1200px] border-t border-line px-6 py-10 text-[13px] text-muted">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
        <div>
          AgentGuard AI · Prototype built at BUILDATHON – Future Forge 2026
        </div>
        <div className="max-w-[500px]">
          Execution authorization and governance layer for autonomous AI. Simulated data is illustrative.
        </div>
      </div>
    </footer>
  );
};
