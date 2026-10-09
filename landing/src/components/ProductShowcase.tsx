import React from 'react';
import { Check } from 'lucide-react';

export const ProductShowcase: React.FC = () => {
  return (
    <section className="flex flex-col items-center px-6 pt-16">
      {/* 1200px Wide Showcase Container */}
      <div className="flex w-full max-w-[1200px] flex-col items-center justify-center gap-10 rounded-[40px] md:rounded-[48px] bg-surface p-8 sm:p-12 md:p-[60px] lg:h-[640px] lg:flex-row shadow-sm">
        {/* Left Column (~460px): Tall White Card with Soft Shadow */}
        <div className="flex w-full max-w-[460px] flex-col gap-3 rounded-[24px] bg-card p-8 md:p-10 text-left shadow-soft-lg transition-transform duration-200 hover:-translate-y-0.5">
          {/* Agent Title & Placeholder Bar */}
          <div className="text-lg font-semibold text-ink">Finance Agent</div>
          <div className="h-[7px] w-[70%] rounded bg-[#E8E8ED]" />

          {/* ACTION */}
          <div className="mt-3 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
            ACTION
          </div>
          <div className="text-xs font-semibold text-ink leading-normal">
            Process customer refund, target Payment API
          </div>

          {/* PARAMETERS */}
          <div className="mt-2 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
            PARAMETERS
          </div>
          <div className="flex flex-wrap gap-1.5">
            {['Refund', '₹85,000', 'Finance env', 'Human approval'].map((pill, idx) => (
              <span
                key={pill}
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                  idx === 0
                    ? 'bg-brand-soft text-brand-ink'
                    : 'bg-surface text-ink'
                }`}
              >
                {pill}
              </span>
            ))}
          </div>

          {/* POLICY EVIDENCE */}
          <div className="mt-2 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
            POLICY EVIDENCE
          </div>
          <div className="text-xs leading-normal text-ink">
            Disbursements over ₹50,000 exceed automatic threshold{' '}
            <span className="rounded bg-metric px-1.5 py-0.5 font-medium text-ink">
              [approval required]
            </span>
          </div>

          {/* Placeholder lines simulating retrieved policy context */}
          <div className="mt-1 space-y-1.5">
            <div className="h-[7px] w-[94%] rounded bg-[#E8E8ED]" />
            <div className="h-[7px] w-[82%] rounded bg-[#E8E8ED]" />
            <div className="h-[7px] w-[68%] rounded bg-[#E8E8ED]" />
          </div>

          {/* RISK FACTORS */}
          <div className="mt-2 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
            RISK FACTORS
          </div>
          <div className="space-y-1.5">
            <div className="h-[7px] w-[62%] rounded bg-[#D9D9DF]" />
            <div className="h-[7px] w-[90%] rounded bg-[#D9D9DF]" />
            <div className="h-[7px] w-[76%] rounded bg-[#D9D9DF]" />
          </div>
        </div>

        {/* Right Column (~360px): Three Stacked Cards */}
        <div className="flex w-full max-w-[360px] flex-col gap-4 text-left">
          {/* Card (a): Execution Authorization with Score 76, amber REVIEW badge, and purple bars */}
          <div className="rounded-[22px] bg-card p-7 shadow-soft transition-transform duration-200 hover:-translate-y-0.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-muted">Execution authorization</span>
              <span className="rounded-full border border-warn/30 bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-warn">
                REVIEW
              </span>
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-[64px] font-bold tracking-tight text-ink leading-none">
                76
              </span>
              <span className="text-lg text-muted">/ 100</span>
            </div>

            <div className="mt-4 flex flex-col gap-2">
              {[
                { width: '88%', label: 'Deterministic rules' },
                { width: '42%', label: 'Risk analyzer score' },
                { width: '76%', label: 'Cumulative spend cap' },
              ].map((bar, idx) => (
                <div key={idx} className="h-1.5 w-full rounded bg-surface">
                  <div
                    className="h-1.5 rounded bg-brand transition-all duration-700"
                    style={{ width: bar.width }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Card (b): Policy Checks Completed with Pale Green Circle Check */}
          <div className="flex items-center gap-3.5 rounded-[22px] bg-card px-7 py-6 shadow-soft transition-transform duration-200 hover:-translate-y-0.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ok-soft text-ok">
              <Check size={20} className="stroke-[2.5]" />
            </span>
            <div>
              <div className="font-semibold text-ink text-[15px]">Policy checks completed</div>
              <div className="mt-0.5 text-[13px] text-muted">
                Human approval required before execution
              </div>
            </div>
          </div>

          {/* Card (c): Pale Cyan Card (no shadow) */}
          <div className="rounded-[22px] bg-learn-soft px-7 py-6 text-learn-ink transition-transform duration-200 hover:-translate-y-0.5">
            <div className="text-[13px] font-medium text-learn">Required next step</div>
            <div className="mt-1 text-xl font-bold text-ink">Human approval</div>
            <div className="mt-0.5 text-[13px] font-medium text-learn">
              Hash-bound · single-use
            </div>
          </div>
        </div>
      </div>

      {/* Label under container */}
      <p className="mt-3.5 text-center text-xs text-muted">Demo data (simulated)</p>
    </section>
  );
};
