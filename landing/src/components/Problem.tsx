import React from 'react';

export const Problem: React.FC = () => {
  return (
    <section id="problem" className="flex flex-col items-center gap-5 px-6 pt-36 text-center">
      {/* Purple eyebrow label (sentence case) */}
      <p className="text-[15px] font-medium text-brand">The problem</p>

      {/* Headline ~64px, two lines */}
      <h2 className="max-w-[860px] text-4xl sm:text-[54px] lg:text-[64px] font-bold leading-[1.05] tracking-[-0.04em] text-ink">
        Agents can be talked into
        <br />
        things they should never do.
      </h2>

      {/* Muted two-line paragraph */}
      <p className="max-w-[640px] text-lg sm:text-[20px] leading-relaxed text-muted">
        Outside text can steer an agent into refunds, exports or payments, and tool permissions alone
        do not check whether a specific action is safe.
      </p>
    </section>
  );
};
