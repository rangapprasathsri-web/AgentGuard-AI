import React from 'react';

const steps = [
  {
    number: '01',
    title: 'Connect your website',
    description: 'Register protected actions, allowed parameters, and sliding spend ceilings in policy files.',
  },
  {
    number: '02',
    title: 'Set approvers',
    description: 'Choose which roles review risky escalations and configure secure human-in-the-loop notifications.',
  },
  {
    number: '03',
    title: 'Route the agent',
    description: 'Point agent tools at the AgentGuard Gateway. Keep enterprise API credentials safely isolated.',
  },
  {
    number: '04',
    title: 'Watch it decide',
    description: 'ALLOW, REVIEW or BLOCK with a cryptographic HMAC audit trail on every autonomous proposal.',
  },
];

export const HowItWorks: React.FC = () => {
  return (
    <section id="how" className="flex flex-col items-center px-6 pt-36 text-center">
      {/* Eyebrow Label */}
      <p className="text-[15px] font-medium text-brand">How it works</p>

      {/* Headline */}
      <h2 className="mt-3 text-4xl sm:text-[54px] lg:text-[60px] font-bold tracking-[-0.04em] text-ink leading-tight">
        Four steps. A few minutes.
      </h2>

      {/* 4 Columns (Stacked on mobile, 2 cols on tablet, 4 cols on desktop) */}
      <ol className="mt-16 grid w-full max-w-[1200px] gap-10 sm:grid-cols-2 lg:grid-cols-4 text-left">
        {steps.map((step) => (
          <li key={step.number} className="border-t border-hair pt-6 transition-all">
            <div className="font-mono text-sm text-muted">{step.number}</div>
            <div className="mt-3 text-xl font-bold tracking-[-0.01em] text-ink">
              {step.title}
            </div>
            <p className="mt-2 text-[15px] leading-relaxed text-muted">
              {step.description}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
};
