import React from 'react';
import { Logo } from './Logo';

export const FinalCta: React.FC = () => {
  const scrollTo = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="px-6">
      <div className="mx-auto mt-36 flex max-w-[1200px] flex-col items-center gap-7 rounded-[48px] bg-surface px-8 py-24 text-center shadow-sm">
        {/* Centered Logo Mark */}
        <Logo size={60} />

        {/* Headline ~72px, Two Lines */}
        <h2 className="max-w-[920px] text-4xl sm:text-[54px] lg:text-[72px] font-bold leading-[1.02] tracking-[-0.045em] text-ink">
          Put authorization between
          <br />
          AI intent and execution.
        </h2>

        {/* Purple Pill Button */}
        <button
          type="button"
          onClick={() => scrollTo('demo')}
          id="cta-explore-btn"
          className="mt-2 flex h-[52px] items-center rounded-full bg-brand px-8 text-[17px] font-medium text-white transition-colors hover:bg-brand-hover shadow-sm"
        >
          Explore the Platform
        </button>
      </div>
    </section>
  );
};
