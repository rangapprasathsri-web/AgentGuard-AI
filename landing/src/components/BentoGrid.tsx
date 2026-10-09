import { ShieldCheck, Check, Ban, AlertTriangle } from 'lucide-react';

export const BentoGrid: React.FC = () => {
  return (
    <section id="features" className="flex flex-col items-center px-6 pt-36 text-center">
      {/* Eyebrow Label */}
      <p className="text-[15px] font-medium text-brand">What AgentGuard does</p>

      {/* Headline ~64px */}
      <h2 className="mt-3 text-4xl sm:text-[54px] lg:text-[64px] font-bold tracking-[-0.04em] text-ink leading-tight">
        Decide. Enforce. Prove.
      </h2>

      {/* Bento Grid: 20px gap, 2 rows of unequal widths, radius ~40px */}
      <div className="mt-14 grid w-full max-w-[1200px] gap-5 grid-cols-1 lg:grid-cols-3 text-left">
        {/* ROW 1 - CARD 1: Wide Gray Card (~65%) */}
        <div className="lg:col-span-2 flex min-h-[420px] flex-col justify-between gap-8 rounded-[40px] bg-surface p-10 sm:p-12 transition-transform duration-200 hover:-translate-y-0.5">
          <div>
            <h3 className="text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">
              Every action, checked.
            </h3>
            <p className="mt-2.5 max-w-[540px] text-[17px] leading-relaxed text-muted">
              Independent deterministic rules, real-time risk scoring, and cumulative spend gates
              inspect the canonical payload before anything reaches your production tools.
            </p>
          </div>

          <div className="flex flex-col gap-3.5">
            {/* Small White Pills */}
            <div className="flex flex-wrap gap-2">
              {['Policy rules', 'Risk score', 'Cumulative limit'].map((pill) => (
                <span
                  key={pill}
                  className="rounded-full bg-card px-4 py-1.5 text-sm font-medium text-ink shadow-[0_1px_4px_rgba(0,0,0,0.05)]"
                >
                  {pill}
                </span>
              ))}
            </div>

            {/* White Mini-Card: split refund struck through + REVIEW result */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-[20px] bg-card px-6 py-5 shadow-soft">
              <div className="flex items-center gap-3">
                <span className="text-sm font-mono text-muted line-through">
                  POST /refunds amount: ₹95,000 (split-refund attempt)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-warn/30 bg-warn-soft px-3 py-1 text-xs font-semibold text-warn">
                  REVIEW · Cumulative limit flagged
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ROW 1 - CARD 2: Narrow Gray Card (~35%) */}
        <div className="lg:col-span-1 flex min-h-[420px] flex-col justify-between gap-8 rounded-[40px] bg-surface p-10 sm:p-12 transition-transform duration-200 hover:-translate-y-0.5">
          <div>
            <h3 className="text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">
              Humans decide the risky ones.
            </h3>
            <p className="mt-2.5 text-[17px] leading-relaxed text-muted">
              When an action exceeds risk thresholds, AgentGuard halts execution until an authorized human signs off.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-ok-soft text-ok shadow-sm">
              <ShieldCheck size={32} className="stroke-[2.2]" />
            </span>
            <div>
              <div className="text-[26px] font-bold tracking-tight text-ink">1 approval, 1 use</div>
              <div className="text-sm text-muted">Single-use · Hash-bound token</div>
            </div>
          </div>
        </div>

        {/* ROW 2 - CARD 1: Narrow Cyan Card (~35%) */}
        <div className="lg:col-span-1 flex min-h-[420px] flex-col justify-between gap-8 rounded-[40px] bg-learn-soft p-10 sm:p-12 transition-transform duration-200 hover:-translate-y-0.5">
          <div>
            <h3 className="text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">
              Know why it was blocked.
            </h3>
            <p className="mt-2.5 text-[17px] leading-relaxed text-learn">
              Deterministic evidence and exact policy excerpts show operators why each refusal occurred.
            </p>
          </div>

          <ul className="flex flex-col gap-3 text-[15px] font-medium text-ink">
            <li className="flex items-center gap-3">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-learn text-white">
                <Check size={13} className="stroke-[3]" />
              </span>
              <span>Disbursement cap exceeded without approval</span>
            </li>
            <li className="flex items-center gap-3 text-muted">
              <span className="h-5 w-5 rounded-md border-[1.5px] border-learn/50" />
              <span>Prompt injection pattern detected</span>
            </li>
            <li className="flex items-center gap-3 text-muted">
              <span className="h-5 w-5 rounded-md border-[1.5px] border-learn/50" />
              <span>Target store flagged production-critical</span>
            </li>
          </ul>
        </div>

        {/* ROW 2 - CARD 2: Wide Gray Card (~65%) */}
        <div className="lg:col-span-2 flex min-h-[420px] flex-col justify-between gap-8 rounded-[40px] bg-surface p-10 sm:p-12 transition-transform duration-200 hover:-translate-y-0.5">
          <div>
            <h3 className="text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">
              One gateway. Every tool.
            </h3>
            <p className="mt-2.5 max-w-[540px] text-[17px] leading-relaxed text-muted">
              Point every departmental agent to the AgentGuard Gateway. Keep enterprise API credentials
              isolated where autonomous models can never touch them.
            </p>
          </div>

          {/* Three Small White Mini-Cards */}
          <div className="grid gap-3.5 sm:grid-cols-3">
            {[
              {
                tool: 'Refund',
                target: 'Payments API',
                verdict: 'ALLOW',
                badgeClass: 'bg-ok-soft text-ok',
                icon: Check,
              },
              {
                tool: 'Payment',
                target: 'Disbursement Hub',
                verdict: 'REVIEW',
                badgeClass: 'bg-warn-soft text-warn border border-warn/25',
                icon: AlertTriangle,
              },
              {
                tool: 'Export',
                target: 'Prod Customers DB',
                verdict: 'BLOCK',
                badgeClass: 'bg-bad-soft text-bad',
                icon: Ban,
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.tool} className="rounded-[20px] bg-card p-5 shadow-soft">
                  <div className="flex items-center justify-between">
                    <span className="text-[15px] font-semibold text-ink">{item.tool}</span>
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${item.badgeClass}`}>
                      <Icon size={12} className="stroke-[2.5]" />
                      {item.verdict}
                    </span>
                  </div>
                  <div className="mt-3 text-xs text-muted font-mono">{item.target}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Row Below the Grid: "Also included" + Gray Pills */}
      <div className="mt-10 flex max-w-[1200px] flex-wrap items-center justify-center gap-2.5 text-[15px]">
        <span className="mr-1 text-muted">Also included</span>
        {[
          'Tamper-evident audit log',
          'Policy evidence (RAG)',
          'Per-tenant limits',
          'Fail-closed execution',
          'Approval inbox',
        ].map((feature) => (
          <span
            key={feature}
            className="rounded-full bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-line"
          >
            {feature}
          </span>
        ))}
      </div>
    </section>
  );
};
