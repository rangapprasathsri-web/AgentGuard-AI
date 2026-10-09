import React, { useState } from 'react';
import { Lock } from 'lucide-react';

interface Scenario {
  id: 'ALLOW' | 'REVIEW' | 'BLOCK';
  name: string;
  agent: string;
  action: string;
  target: string;
  score: number;
  verdict: 'ALLOW' | 'REVIEW' | 'BLOCK';
  verdictLabel: string;
  badgeClass: string;
  evidence: string;
  highlightedChip: string;
  reason: string;
  nextStepTitle: string;
  nextStepSubtitle: string;
  nextStepBg: string;
  nextStepColor: string;
  rulePassed: boolean;
  scoreBars: { label: string; pct: number }[];
}

const scenarios: Record<'ALLOW' | 'REVIEW' | 'BLOCK', Scenario> = {
  ALLOW: {
    id: 'ALLOW',
    name: 'Routine Order Lookup',
    agent: 'Analytics Agent',
    action: 'SELECT order_id, status, amount FROM orders WHERE id = 4091',
    target: 'Read Replica (Orders DB)',
    score: 14,
    verdict: 'ALLOW',
    verdictLabel: 'ALLOW (Automated pass)',
    badgeClass: 'bg-ok-soft text-ok border-ok/20',
    evidence: 'Queries against read replicas within rate ceiling are pre-authorized by tenant rule 04.',
    highlightedChip: '[pre-authorized]',
    reason: 'Zero mutation, non-sensitive classification, under query budget.',
    nextStepTitle: 'Immediate execution',
    nextStepSubtitle: 'Cryptographic HMAC log signed & routed',
    nextStepBg: 'bg-ok-soft',
    nextStepColor: 'text-ok',
    rulePassed: true,
    scoreBars: [
      { label: 'Deterministic checks', pct: 10 },
      { label: 'Risk analyzer score', pct: 15 },
      { label: 'Rate / cumulative spend', pct: 18 },
    ],
  },
  REVIEW: {
    id: 'REVIEW',
    name: 'Customer Refund ₹85,000',
    agent: 'Finance Agent',
    action: 'POST /refunds - account: CUST-8219, amount: ₹85,000',
    target: 'Payment Gateway API',
    score: 76,
    verdict: 'REVIEW',
    verdictLabel: 'REVIEW (Approval required)',
    badgeClass: 'bg-warn-soft text-warn border-warn/30',
    evidence: 'Refunds exceeding ₹50,000 require two-party authorization before payment tool dispatch.',
    highlightedChip: '[approval required]',
    reason: 'Single transaction exceeds threshold, cumulative 24h spend elevated.',
    nextStepTitle: 'Human approval',
    nextStepSubtitle: 'Hash-bound · single-use token',
    nextStepBg: 'bg-learn-soft',
    nextStepColor: 'text-learn',
    rulePassed: false,
    scoreBars: [
      { label: 'Deterministic checks', pct: 88 },
      { label: 'Risk analyzer score', pct: 45 },
      { label: 'Rate / cumulative spend', pct: 76 },
    ],
  },
  BLOCK: {
    id: 'BLOCK',
    name: 'Production Drop Table Injection',
    agent: 'DevOps Agent',
    action: 'DROP TABLE customers_prod; -- injected via untrusted support ticket',
    target: 'Production Database',
    score: 99,
    verdict: 'BLOCK',
    verdictLabel: 'BLOCK (Hard security refusal)',
    badgeClass: 'bg-bad-soft text-bad border-bad/30',
    evidence: 'Destructive database mutations on production resources are strictly prohibited by Invariant I8.',
    highlightedChip: '[hard block]',
    reason: 'Prompt injection markers identified; unauthorized schema teardown attempt.',
    nextStepTitle: 'Execution terminated',
    nextStepSubtitle: 'Fail-closed · Incident logged to ledger',
    nextStepBg: 'bg-bad-soft',
    nextStepColor: 'text-bad',
    rulePassed: false,
    scoreBars: [
      { label: 'Deterministic checks', pct: 100 },
      { label: 'Risk analyzer score', pct: 98 },
      { label: 'Rate / cumulative spend', pct: 99 },
    ],
  },
};

export const InteractiveDemo: React.FC = () => {
  const [selectedId, setSelectedId] = useState<'ALLOW' | 'REVIEW' | 'BLOCK'>('REVIEW');
  const scenario = scenarios[selectedId];

  return (
    <section id="demo" className="flex flex-col items-center px-6 pt-36 text-center">
      {/* Eyebrow Label */}
      <p className="text-[15px] font-medium text-brand">Interactive demo</p>

      {/* Headline */}
      <h2 className="mt-3 text-4xl sm:text-[54px] lg:text-[60px] font-bold tracking-[-0.04em] text-ink leading-tight">
        Simulate live governance in action.
      </h2>

      {/* Paragraph */}
      <p className="mt-4 max-w-[620px] text-[17px] leading-relaxed text-muted">
        Select a simulated agent scenario to inspect how AgentGuard evaluates policy rules,
        calculates multi-dimensional risk, and gates execution.
      </p>

      {/* Segmented Control Bar */}
      <div className="mt-10 inline-flex max-w-full gap-2 rounded-full bg-surface p-1.5 shadow-sm border border-line">
        {(['ALLOW', 'REVIEW', 'BLOCK'] as const).map((key) => {
          const isSelected = selectedId === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setSelectedId(key)}
              aria-pressed={isSelected}
              className={`flex h-11 items-center gap-2 rounded-full px-6 text-sm font-semibold transition-all ${
                isSelected
                  ? 'bg-card text-ink shadow-soft'
                  : 'text-muted hover:text-ink'
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  key === 'ALLOW'
                    ? 'bg-ok-dot'
                    : key === 'REVIEW'
                    ? 'bg-warn-dot'
                    : 'bg-bad-dot'
                }`}
              />
              Scenario {key}
            </button>
          );
        })}
      </div>

      {/* Main Container styled like Showcase */}
      <div className="mt-8 flex w-full max-w-[1200px] flex-col items-center justify-center gap-10 rounded-[40px] md:rounded-[48px] bg-surface p-8 sm:p-12 md:p-[60px] lg:h-[620px] lg:flex-row shadow-sm text-left">
        {/* Left Card: Agent Request & Policy Inspection */}
        <div className="flex w-full max-w-[460px] flex-col justify-between gap-4 rounded-[24px] bg-card p-8 md:p-10 shadow-soft-lg transition-all duration-300">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-lg font-semibold text-ink">{scenario.agent}</span>
              <span className="text-xs font-mono text-muted">{scenario.target}</span>
            </div>

            <div className="mt-3.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
              PROPOSED ACTION
            </div>
            <div className="mt-1 rounded-xl bg-surface p-3 font-mono text-xs text-ink break-all">
              {scenario.action}
            </div>

            <div className="mt-3.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
              POLICY EVIDENCE (RAG)
            </div>
            <div className="mt-1 text-xs leading-normal text-ink">
              {scenario.evidence}{' '}
              <span className="rounded bg-metric px-1.5 py-0.5 font-medium text-ink">
                {scenario.highlightedChip}
              </span>
            </div>

            <div className="mt-3.5 text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
              OPERATIONAL RATIONALE
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              {scenario.reason}
            </p>
          </div>

          <div className="flex items-center gap-2 pt-2 border-t border-line text-xs text-muted">
            <Lock size={12} className="stroke-[2]" />
            <span>Agent holds 0 credentials · Gateway verifies HMAC</span>
          </div>
        </div>

        {/* Right Stacked Cards */}
        <div className="flex w-full max-w-[360px] flex-col gap-4">
          {/* Card 1: Score & Verdict */}
          <div className="rounded-[22px] bg-card p-7 shadow-soft transition-all duration-300">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-muted">Risk assessment</span>
              <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${scenario.badgeClass}`}>
                {scenario.verdict}
              </span>
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-[64px] font-bold tracking-tight text-ink leading-none">
                {scenario.score}
              </span>
              <span className="text-lg text-muted">/ 100</span>
            </div>

            {/* Score bars */}
            <div className="mt-4 flex flex-col gap-2">
              {scenario.scoreBars.map((bar, idx) => (
                <div key={idx}>
                  <div className="flex justify-between text-[11px] text-muted mb-1">
                    <span>{bar.label}</span>
                    <span className="font-mono">{bar.pct}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded bg-surface">
                    <div
                      className={`h-1.5 rounded transition-all duration-700 ${
                        selectedId === 'ALLOW'
                          ? 'bg-ok'
                          : selectedId === 'REVIEW'
                          ? 'bg-brand'
                          : 'bg-bad'
                      }`}
                      style={{ width: `${bar.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 2: Next Step State */}
          <div className={`rounded-[22px] ${scenario.nextStepBg} px-7 py-6 transition-all duration-300`}>
            <div className={`text-[13px] font-medium ${scenario.nextStepColor}`}>Required next step</div>
            <div className="mt-1 text-xl font-bold text-ink">{scenario.nextStepTitle}</div>
            <div className={`mt-0.5 text-[13px] font-medium ${scenario.nextStepColor}`}>
              {scenario.nextStepSubtitle}
            </div>
          </div>
        </div>
      </div>

      <p className="mt-3.5 text-center text-xs text-muted">
        Simulated · No real tools or databases are executed in this preview
      </p>
    </section>
  );
};
