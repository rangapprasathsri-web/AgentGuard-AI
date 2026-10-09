import React from 'react';
import { Logo } from './Logo';

export const Hero: React.FC = () => {
  const scrollTo = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="flex flex-col items-center px-6 pt-20 text-center md:pt-28">
      <div className="rise flex flex-col items-center gap-7">
        {/* Large Logo Mark ~85px */}
        <Logo size={85} />

        {/* Small Gray Pill Badge with Purple Dot */}
        <span className="inline-flex h-8 items-center gap-2 rounded-full bg-surface px-4 text-[13px] font-medium text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />
          Execution governance for autonomous AI
        </span>

        {/* Two-Line Headline ~100px */}
        <h1 className="max-w-[1100px] text-[52px] font-bold leading-[0.98] tracking-[-0.045em] sm:text-[76px] lg:text-[100px] text-ink">
          Every AI action.
          <br />
          Verified before execution.
        </h1>

        {/* Two-Line Paragraph ~20px Muted Gray, Max ~640px */}
        <p className="max-w-[640px] text-lg leading-relaxed text-muted sm:text-[20px]">
          Deterministic guardrails, sliding cumulative limits, and human-in-the-loop approvals
          preventing rogue agent execution across enterprise tools.
        </p>

        {/* Action Buttons Side-by-Side */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-6">
          <button
            type="button"
            onClick={() => scrollTo('demo')}
            id="hero-explore-btn"
            className="flex h-[52px] items-center rounded-full bg-brand px-8 text-[17px] font-medium text-white transition-colors hover:bg-brand-hover shadow-sm"
          >
            Explore the Platform
          </button>
          <button
            type="button"
            onClick={() => scrollTo('how')}
            className="text-[17px] font-medium text-brand transition-colors hover:text-brand-hover"
          >
            See how it works ›
          </button>
        </div>
      </div>
    </section>
  );
};
