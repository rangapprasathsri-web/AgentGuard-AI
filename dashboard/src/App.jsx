import React, { useState, useEffect } from 'react';
import { 
  Shield, AlertTriangle, CheckCircle, XCircle, Clock, 
  Terminal, Database, Lock, RefreshCw, FileText, UserCheck, 
  Layers, ChevronRight, AlertOctagon, Cpu, Hash, Play,
  Search, ShieldAlert, Check, X, Eye, ExternalLink, Power, Info
} from 'lucide-react';

const InfoTooltip = ({ text }) => (
  <div className="relative group inline-flex items-center ml-1.5 cursor-help z-50 align-middle">
    <Info className="w-3.5 h-3.5 text-slate-500 hover:text-emerald-400 transition-colors" />
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-xs text-slate-200 rounded-lg shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all pointer-events-none border border-slate-600 whitespace-normal text-left font-normal z-[100] leading-relaxed">
      {text}
      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
    </div>
  </div>
);

const GUARD_API = 'http://localhost:8001';
const GATEWAY_API = 'http://localhost:8002';
const DEMO_API = 'http://localhost:8004';
const AGENTS_API = 'http://localhost:8003';

import { initializeApp } from "firebase/app";
import { getFirestore, collection, onSnapshot, query, orderBy, limit, doc } from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

let db = null;
if (firebaseConfig.apiKey) {
  try {
    const app = initializeApp(firebaseConfig);
    db = getFirestore(app);
  } catch (e) {
    console.warn("Firebase init failed", e);
  }
}

export default function App() {
  const [firebaseOffline, setFirebaseOffline] = useState(!db);
  const [metricsSummary, setMetricsSummary] = useState(null);

  const [activeTab, setActiveTab] = useState('feed');
  const [currentRole, setCurrentRole] = useState('approver');
  const [currentActor, setCurrentActor] = useState('approver_cfo');
  
  // Data states
  const [decisions, setDecisions] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [auditVerify, setAuditVerify] = useState({ valid: true, records_checked: 0, head_hash: 'GENESIS' });
  const [agents, setAgents] = useState({});
  const [resources, setResources] = useState({});
  const [policyVersion, setPolicyVersion] = useState('');
  
  // Selection states
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectingId, setRejectingId] = useState(null);
  
  // Scenario Runner states
  const [runningScenario, setRunningScenario] = useState(null);
  const [scenarioResults, setScenarioResults] = useState({});
  const [tampering, setTampering] = useState(false);
  const [resetting, setResetting] = useState(false);

  // Filters
  const [filterDecision, setFilterDecision] = useState('ALL');
  const [auditFilter, setAuditFilter] = useState('');

  // Auto-poll every 2 seconds or use Firebase
  useEffect(() => {
    let unsubs = [];
    
    if (db && !firebaseOffline) {
      try {
        const decisionsQ = query(collection(db, "decisions"), orderBy("ts", "desc"), limit(50));
        unsubs.push(onSnapshot(decisionsQ, (snapshot) => {
          const newDecs = [];
          snapshot.forEach(docSnap => {
            const data = docSnap.data();
            newDecs.push({
              decision_id: docSnap.id,
              ...data,
              created_at: data.ts,
              decision_source: 'firebase_mirror',
              action_hash: 'not_mirrored',
              risk_level: 'unknown',
              response: { factors: data.reasons }
            });
          });
          setDecisions(newDecs);
        }, (err) => setFirebaseOffline(true)));

        const approvalsQ = query(collection(db, "approvals"), orderBy("created_at", "desc"), limit(50));
        unsubs.push(onSnapshot(approvalsQ, (snapshot) => {
          const newApps = [];
          snapshot.forEach(docSnap => newApps.push({id: docSnap.id, ...docSnap.data()}));
          setApprovals(newApps);
        }, (err) => setFirebaseOffline(true)));

        const summaryDoc = doc(db, "metrics", "summary");
        unsubs.push(onSnapshot(summaryDoc, (docSnap) => {
          if (docSnap.exists()) {
             setMetricsSummary(docSnap.data());
          }
        }, (err) => setFirebaseOffline(true)));
      } catch (err) {
        setFirebaseOffline(true);
      }
    }
    
    // Initial fetch for non-mirrored stuff
    fetchData();
    const interval = setInterval(() => {
       if (firebaseOffline || !db) {
         fetchData();
       } else {
         fetchNonMirrored();
       }
    }, 2000);
    
    return () => {
      clearInterval(interval);
      unsubs.forEach(u => u());
    };
  }, [currentRole, currentActor, firebaseOffline]);

  const fetchNonMirrored = async () => {
    try {
      const headers = getHeaders();
      // Only fetch audit, agents, resources, policy
      const audRes = await fetch(`${GUARD_API}/audit?limit=50`, { headers });
      if (audRes.ok) setAuditEvents(await audRes.json());
      const verRes = await fetch(`${GUARD_API}/audit/verify`, { headers });
      if (verRes.ok) setAuditVerify(await verRes.json());
      const agRes = await fetch(`${GUARD_API}/agents`, { headers });
      if (agRes.ok) setAgents(await agRes.json());
      const resRes = await fetch(`${GUARD_API}/resources`, { headers });
      if (resRes.ok) setResources(await resRes.json());
      const polRes = await fetch(`${GUARD_API}/policy/version`, { headers });
      if (polRes.ok) setPolicyVersion((await polRes.json()).policy_version);
    } catch (e) {}
  };

  const getHeaders = () => ({
    'X-Role': currentRole,
    'X-Actor': currentActor,
  });

  const fetchData = async () => {
    try {
      const headers = getHeaders();
      // 1. Fetch decisions
      const decRes = await fetch(`${GUARD_API}/decisions`, { headers });
      if (decRes.ok) setDecisions(await decRes.json());
      else setDecisions([]);

      // 2. Fetch approvals
      const appRes = await fetch(`${GUARD_API}/approvals`, { headers });
      if (appRes.ok) setApprovals(await appRes.json());
      else setApprovals([]);

      // 3. Fetch audit log
      const audRes = await fetch(`${GUARD_API}/audit?limit=50`, { headers });
      if (audRes.ok) setAuditEvents(await audRes.json());
      else setAuditEvents([]);

      // 4. Fetch audit verification
      const verRes = await fetch(`${GUARD_API}/audit/verify`, { headers });
      if (verRes.ok) setAuditVerify(await verRes.json());
      else setAuditVerify({ valid: false, reason: "Access Denied", records_checked: 0, head_hash: "N/A" });

      // 5. Fetch agents and resources
      const agRes = await fetch(`${GUARD_API}/agents`, { headers });
      if (agRes.ok) setAgents(await agRes.json());
      else setAgents({});

      const resRes = await fetch(`${GUARD_API}/resources`, { headers });
      if (resRes.ok) setResources(await resRes.json());
      else setResources({});

      const polRes = await fetch(`${GUARD_API}/policy/version`, { headers });
      if (polRes.ok) {
        const d = await polRes.json();
        setPolicyVersion(d.policy_version);
      } else {
        setPolicyVersion("Unauthorized");
      }
    } catch (e) {
      // Backend may be starting or offline
    }
  };

  const handleApprove = async (id) => {
    try {
      await fetch(`${GUARD_API}/approvals/${id}/decide`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'APPROVE', reason: 'Approved via Governance Dashboard' }),
      });
      fetchData();
    } catch (e) {
      alert('Approval failed: ' + e.message);
    }
  };

  const handleReject = async (id) => {
    try {
      await fetch(`${GUARD_API}/approvals/${id}/decide`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'REJECT', reason: rejectReason || 'Rejected by operator' }),
      });
      setRejectingId(null);
      setRejectReason('');
      fetchData();
    } catch (e) {
      alert('Rejection failed: ' + e.message);
    }
  };

  const toggleAgentStatus = async (agentId, currentStatus) => {
    if (currentRole !== 'admin') {
      alert('Kill switch requires ADMIN role!');
      return;
    }
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    try {
      await fetch(`${GUARD_API}/admin/agents/${agentId}/status`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchData();
    } catch (e) {
      alert('Status update failed: ' + e.message);
    }
  };

  const handleTamperDemo = async () => {
    setTampering(true);
    try {
      const res = await fetch(`${GUARD_API}/audit/demo/tamper`, { method: 'POST', headers: getHeaders() });
      if (res.ok) {
        alert('Tampered 1 row in audit table directly via SQL! Notice the Chain Status turn broken.');
      } else {
        alert('Tamper demo endpoint returned error or requires DEMO_MODE.');
      }
      fetchData();
    } catch (e) {
      alert('Tamper error: ' + e.message);
    } finally {
      setTampering(false);
    }
  };

  const handleResetDemo = async () => {
    setResetting(true);
    try {
      await fetch(`${GUARD_API}/demo/reset`, { method: 'POST', headers: getHeaders() });
      alert('Environment restored: audit row restored, databases cleaned, tools reseeded.');
      fetchData();
    } catch (e) {
      alert('Reset error: ' + e.message);
    } finally {
      setResetting(false);
    }
  };

  const handleRunScenario = async (id) => {
    setRunningScenario(id);
    try {
      const res = await fetch(`${DEMO_API}/demo/run/${id}`, { method: 'POST' });
      const data = await res.json();
      setScenarioResults(prev => ({ ...prev, [id]: data }));
      fetchData();
    } catch (e) {
      setScenarioResults(prev => ({ ...prev, [id]: { error: e.message } }));
    } finally {
      setRunningScenario(null);
    }
  };

  // Helper styles
  const getDecisionBadge = (decision) => {
    if (decision === 'ALLOW') return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">ALLOW</span>;
    if (decision === 'REVIEW') return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">REVIEW</span>;
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">BLOCK</span>;
  };

  const filteredDecisions = decisions.filter(d => {
    if (filterDecision === 'ALL') return true;
    return d.decision === filterDecision;
  });

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                AgentGuard AI
              </span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 bg-emerald-950 border border-emerald-800 text-emerald-400 rounded">
                v1.0 Vertical Slice
              </span>
            </div>
            <p className="text-xs text-slate-400">Execution Authorization & Governance Layer</p>
          </div>
        </div>

        {/* Global Security Badges */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs">
            {firebaseOffline ? (
              <span className="flex items-center text-rose-400 font-semibold space-x-1">
                <XCircle className="w-3.5 h-3.5" />
                <span>FIREBASE OFFLINE</span>
              </span>
            ) : (
              <span className="flex items-center text-emerald-400 font-semibold space-x-1 animate-pulse">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
                <span>LIVE MIRROR</span>
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs">
            <span className="text-slate-400 font-medium flex items-center">
              Audit Chain
              <InfoTooltip text="The HMAC Hash Chain ensures that past logs, approvals, and decisions cannot be tampered with or deleted by an attacker or rogue agent." />:
            </span>
            {auditVerify.valid ? (
              <span className="flex items-center text-emerald-400 font-semibold space-x-1">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>INTACT</span>
              </span>
            ) : (
              <span className="flex items-center text-rose-400 font-semibold space-x-1 animate-pulse">
                <AlertOctagon className="w-3.5 h-3.5" />
                <span>BROKEN (TAMPERED)</span>
              </span>
            )}
            <span className="font-mono text-[10px] text-slate-500 border-l border-slate-800 pl-2">
              {auditVerify.records_checked} events
            </span>
          </div>

          {/* Role Switcher */}
          <div className="flex items-center space-x-2 bg-slate-900/90 border border-slate-800 rounded-lg p-1">
            <span className="text-xs text-slate-400 pl-2 pr-1 font-medium">Role:</span>
            {['approver', 'admin', 'operator', 'agent'].map((role) => (
              <button
                key={role}
                onClick={() => {
                  setCurrentRole(role);
                  setCurrentActor(role === 'admin' ? 'admin_1' : role === 'approver' ? 'approver_cfo' : 'operator_1');
                }}
                className={`text-xs px-2.5 py-1 rounded-md font-medium transition-all capitalize ${
                  currentRole === role
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="bg-slate-950/40 border-b border-slate-800 px-6 flex items-center justify-between">
        <nav className="flex space-x-1 py-2">
          {[
            { id: 'feed', label: 'Decisions Feed', icon: Layers, badge: decisions.length },
            { id: 'approvals', label: 'Approval Queue', icon: Clock, badge: approvals.filter(a => a.status === 'PENDING').length },
            { id: 'audit', label: 'Audit Log & Chain', icon: FileText },
            { id: 'scenarios', label: 'Demo Scenarios', icon: Play, badge: '15' },
            { id: 'registries', label: 'Agents & Policies', icon: Database },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-slate-800/90 text-emerald-400 border border-slate-700/60 shadow-inner'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.badge !== undefined && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                    isActive ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center space-x-3 text-xs text-slate-400">
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-slate-400">Polling active (2s)</span>
          </span>
          <button 
            onClick={fetchData}
            className="p-1.5 hover:bg-slate-800 rounded-md text-slate-400 hover:text-slate-200 transition"
            title="Refresh now"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {metricsSummary && !firebaseOffline && (
        <div className="bg-slate-900 border-b border-slate-800 p-3 flex justify-between text-xs px-6">
          <span className="text-slate-400">Total Allowed: <strong className="text-emerald-400">{metricsSummary.allow_count || 0}</strong></span>
          <span className="text-slate-400">Total Reviewed: <strong className="text-amber-400">{metricsSummary.review_count || 0}</strong></span>
          <span className="text-slate-400">Total Blocked: <strong className="text-rose-400">{metricsSummary.block_count || 0}</strong></span>
          <span className="text-slate-400">Pending Approvals: <strong className="text-blue-400">{metricsSummary.pending_approvals || 0}</strong></span>
          <span className="text-slate-400">Blocked Value: <strong className="text-rose-400">₹{metricsSummary.blocked_amount_inr || 0}</strong></span>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 p-6 overflow-auto">
        {/* TAB 1: DECISIONS FEED */}
        {activeTab === 'feed' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div className="flex items-center space-x-2">
                  <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center">
                    Evaluation Stream
                    <InfoTooltip text="Real-time stream of all agent actions evaluated by the Guard's Rule and Policy engines. If an action breaches risk limits, it is flagged for REVIEW or BLOCK." />
                  </h2>
                  <span className="text-xs text-slate-500 font-mono">({filteredDecisions.length} events)</span>
                </div>
                {/* Decision Filters */}
                <div className="flex space-x-1 text-xs">
                  {['ALL', 'ALLOW', 'REVIEW', 'BLOCK'].map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilterDecision(f)}
                      className={`px-2.5 py-1 rounded-md font-medium transition ${
                        filterDecision === f ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              {filteredDecisions.length === 0 ? (
                <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
                  No decisions evaluated yet. Run a scenario from the Demo Scenarios tab.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {filteredDecisions.map((d) => (
                    <div
                      key={d.decision_id}
                      onClick={() => setSelectedDecision(d)}
                      className={`p-4 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                        selectedDecision?.decision_id === d.decision_id
                          ? 'border-emerald-500/50 bg-slate-900/90 shadow-md shadow-emerald-500/5'
                          : 'border-slate-800/80 bg-slate-900/40 hover:bg-slate-900/80 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center space-x-3.5">
                        <div className="flex flex-col items-center justify-center w-12 text-center">
                          {getDecisionBadge(d.decision)}
                          <span className="text-[10px] font-mono text-slate-500 mt-1">Score {d.risk_score}</span>
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-semibold text-slate-200">{d.action}</span>
                            <span className="text-sm font-mono text-emerald-400">{d.target}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-xs text-slate-400 mt-0.5">
                            <span className="text-slate-300 font-medium">{d.agent_id}</span>
                            <span>•</span>
                            <span className="text-[11px] font-mono text-slate-500">{d.created_at}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3">
                        <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400">
                          {d.decision_source}
                        </span>
                        <ChevronRight className="w-4 h-4 text-slate-600" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Decision Drawer */}
            <div className="lg:col-span-1">
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 sticky top-24 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-sm font-semibold text-slate-200">Decision Detail Drawer</h3>
                  {selectedDecision && getDecisionBadge(selectedDecision.decision)}
                </div>

                {!selectedDecision ? (
                  <p className="text-xs text-slate-500 text-center py-10">Select an evaluated action to inspect deep governance breakdown.</p>
                ) : (
                  <div className="space-y-4 text-xs">
                    <div>
                      <span className="text-slate-500 font-medium uppercase text-[10px] tracking-wider flex items-center">
                        Decision ID & Hash
                        <InfoTooltip text="Unique cryptographic identifier for this decision. The Action Hash mathematically guarantees the executed action exactly matches what was requested by the agent." />
                      </span>
                      <p className="font-mono text-emerald-400 break-all text-[11px] mt-0.5">{selectedDecision.decision_id}</p>
                      <p className="font-mono text-slate-400 break-all text-[10px] mt-0.5">SHA-256: {selectedDecision.action_hash}</p>
                    </div>

                    <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Agent:</span>
                        <span className="font-semibold text-slate-200">{selectedDecision.agent_id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Action & Target:</span>
                        <span className="font-mono text-slate-200">{selectedDecision.action} on {selectedDecision.target}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400 flex items-center">
                          Risk Score:
                          <InfoTooltip text="Calculated dynamically by the Risk Engine based on environmental context (like data sensitivity, user role, and action time). Actions over threshold require human approval." />
                        </span>
                        <span className="font-bold text-amber-400">{selectedDecision.risk_score} / 100 ({selectedDecision.risk_level})</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Decision Source:</span>
                        <span className="font-mono text-emerald-400">{selectedDecision.decision_source}</span>
                      </div>
                    </div>

                    {/* Risk Factors Breakdown */}
                    {selectedDecision.response?.factors?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-semibold text-[11px] flex items-center">
                          Additive Risk Factors:
                          <InfoTooltip text="A breakdown of which contextual variables contributed to the overall Risk Score." />
                        </span>
                        <ul className="mt-1 space-y-1">
                          {selectedDecision.response.factors.map((f, i) => (
                            <li key={i} className="text-[11px] font-mono text-slate-300 bg-slate-950/40 px-2 py-1 rounded border border-slate-800/60">
                              {f}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Matched Hard Policy Rules */}
                    {selectedDecision.response?.matched_policies?.length > 0 && (
                      <div className="p-2.5 bg-rose-950/20 border border-rose-800/40 rounded-lg">
                        <span className="text-rose-400 font-semibold text-[11px] flex items-center space-x-1">
                          <AlertTriangle className="w-3 h-3 text-rose-400" />
                          <span>Matched Hard Policies:</span>
                        </span>
                        <div className="mt-1.5 space-y-1">
                          {selectedDecision.response.matched_policies.map((p, idx) => (
                            <div key={idx} className="text-[10px]">
                              <span className="font-mono font-bold text-rose-300">[{p.policy_id}]</span> {p.rule_name}
                              <p className="text-slate-400 mt-0.5">{p.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* GenAI Consequence Analyzer Output */}
                    {selectedDecision.response?.consequences?.length > 0 && (
                      <div className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg">
                        <span className="text-slate-300 font-semibold text-[11px]">GenAI Consequence Analysis (Advisory):</span>
                        <ul className="mt-1 list-disc list-inside space-y-0.5 text-slate-400">
                          {selectedDecision.response.consequences.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* RAG Citations */}
                    {selectedDecision.response?.rag_citations?.length > 0 && (
                      <div>
                        <span className="text-slate-400 font-medium text-[10px] uppercase">RAG Evidence Citations</span>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {selectedDecision.response.rag_citations.map((cite, i) => (
                            <span key={i} className="px-1.5 py-0.5 bg-teal-950 border border-teal-800 text-teal-300 font-mono text-[9px] rounded">
                              {cite}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: APPROVAL QUEUE */}
        {activeTab === 'approvals' && (
          <div className="space-y-4 max-w-5xl mx-auto">
            <div className="flex items-center justify-between pb-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center">
                  Human-In-The-Loop Approval Queue
                  <InfoTooltip text="When an agent action exceeds the acceptable risk threshold, it is paused and sent here. Authorizations are single-use and expire after 10 minutes." />
                </h2>
                <p className="text-xs text-slate-400">Single-use, expiring authorizations bound to exact action hash (Invariant I5, I6)</p>
              </div>
              <span className="text-xs px-2.5 py-1 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-lg">
                Requires role: <strong className="font-mono">approver</strong>
              </span>
            </div>

            {approvals.length === 0 ? (
              <div className="p-16 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
                No pending or completed approvals. Run Scenario 2, 5, or 6 to generate review items.
              </div>
            ) : (
              <div className="space-y-4">
                {[...approvals].sort((a,b) => {
                  if(a.status === 'PENDING' && b.status !== 'PENDING') return -1;
                  if(a.status !== 'PENDING' && b.status === 'PENDING') return 1;
                  return new Date(b.created_at) - new Date(a.created_at);
                }).filter(a => a.status === 'PENDING' || a.status === 'EXPIRED').map((appr) => (
                  <div 
                    key={appr.id}
                    className={`p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur space-y-4 ${appr.status !== 'PENDING' ? 'opacity-60' : ''}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-semibold px-2 py-0.5 bg-slate-800 text-slate-200 rounded">
                            {appr.id}
                          </span>
                          <span className={`text-[11px] font-bold px-2 py-0.5 rounded uppercase ${
                            appr.status === 'PENDING' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            appr.status === 'APPROVED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                            appr.status === 'CONSUMED' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-slate-800 text-slate-500'
                          }`}>
                            {appr.status}
                          </span>
                          <span className="text-xs font-bold text-amber-400">
                            Risk Score {appr.risk_score}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">
                          Requested by <strong className="text-slate-200">{appr.agent_id}</strong> • Expires at: {appr.expires_at}
                        </p>
                      </div>

                      {appr.status === 'PENDING' && (
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => handleApprove(appr.id)}
                            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1 shadow"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Approve</span>
                          </button>
                          <button
                            onClick={() => setRejectingId(rejectingId === appr.id ? null : appr.id)}
                            className="px-3 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white rounded-lg text-xs font-semibold flex items-center space-x-1"
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Reject</span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Raw Parameters Display (Section 11) */}
                    <div className="p-3 bg-slate-950/80 border border-slate-800/80 rounded-lg">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center mb-1">
                        Raw Action Parameters (Exact Binding)
                        <InfoTooltip text="These are the exact parameters bound to the cryptographic hash. If the agent later tries to change even one parameter (like increasing the transfer amount), the signature fails and the action is rejected." />:
                      </span>
                      <pre className="text-xs font-mono text-emerald-400 overflow-x-auto">
                        {JSON.stringify(appr.canonical_action, null, 2)}
                      </pre>
                    </div>

                    {/* Rejection input */}
                    {rejectingId === appr.id && (
                      <div className="p-3 bg-rose-950/20 border border-rose-800/40 rounded-lg space-y-2">
                        <label className="text-xs text-rose-300 font-medium">Rejection Reason:</label>
                        <input
                          type="text"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="e.g. Budget ceiling reached, re-check invoice..."
                          className="w-full bg-slate-900 border border-slate-700 px-3 py-1.5 rounded text-xs text-slate-200"
                        />
                        <button
                          onClick={() => handleReject(appr.id)}
                          className="px-3 py-1 bg-rose-600 text-white text-xs font-semibold rounded"
                        >
                          Confirm Rejection
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: AUDIT LOG & TAMPER PROOF */}
        {activeTab === 'audit' && (
          <div className="space-y-4 max-w-6xl mx-auto">
            <div className="flex items-center justify-between pb-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center">
                  Tamper-Evident HMAC Hash Chain Audit Log
                  <InfoTooltip text="A cryptographic ledger where each event includes a hash of the previous event. This guarantees forensic accountability and makes silent deletion or alteration by a compromised agent mathematically impossible." />
                </h2>
                <p className="text-xs text-slate-400">Append-only HMAC-SHA256 linked records (Invariant I9, Section 12)</p>
              </div>

              {/* Tamper / Reset Controls (Demo Mode) */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={fetchData}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium flex items-center space-x-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Verify Chain</span>
                </button>
                <button
                  onClick={handleTamperDemo}
                  disabled={tampering}
                  className="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-800 border border-rose-700 text-rose-200 rounded-lg text-xs font-medium flex items-center space-x-1"
                >
                  <AlertTriangle className="w-3 h-3" />
                  <span>{tampering ? 'Tampering...' : 'Demo Tamper SQL'}</span>
                </button>
                <button
                  onClick={handleResetDemo}
                  disabled={resetting}
                  className="px-3 py-1.5 bg-teal-900/60 hover:bg-teal-800 border border-teal-700 text-teal-200 rounded-lg text-xs font-medium flex items-center space-x-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>{resetting ? 'Resetting...' : 'Demo Reset All'}</span>
                </button>
              </div>
            </div>

            {/* Chain Verification Card */}
            <div className={`p-4 rounded-xl border flex items-center justify-between ${
              auditVerify.valid 
                ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-300' 
                : 'bg-rose-950/30 border-rose-800 text-rose-300 animate-pulse'
            }`}>
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  {auditVerify.valid ? <CheckCircle className="w-5 h-5 text-emerald-400" /> : <AlertOctagon className="w-5 h-5 text-rose-400" />}
                  <span className="font-bold text-sm">
                    {auditVerify.valid ? 'HMAC Hash Chain Intact' : 'CRITICAL: HMAC Chain Tampering Detected!'}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  {auditVerify.reason} • Records Verified: <strong className="text-white">{auditVerify.records_checked}</strong>
                </p>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono text-slate-500 uppercase block">Head Hash</span>
                <span className="text-[11px] font-mono text-slate-300 break-all">{auditVerify.head_hash}</span>
              </div>
            </div>

            {/* Audit Table */}
            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/40">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] font-mono border-b border-slate-800">
                  <tr>
                    <th className="p-3">Seq</th>
                    <th className="p-3">Event Type</th>
                    <th className="p-3">Decision ID</th>
                    <th className="p-3">Timestamp (UTC)</th>
                    <th className="p-3">Payload Summary</th>
                    <th className="p-3">
                      <div className="flex items-center">
                        HMAC Record Hash
                        <InfoTooltip text="SHA-256 hash mathematically binding this specific event to the previous event's hash, creating an unbreakable chain." />
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {auditEvents.map((evt) => (
                    <tr key={evt.seq} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-slate-500 font-bold">#{evt.seq}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          evt.event_type === 'decision_made' ? 'bg-blue-500/10 text-blue-400' :
                          evt.event_type === 'executed' ? 'bg-emerald-500/10 text-emerald-400' :
                          evt.event_type === 'security_signal' ? 'bg-rose-500/10 text-rose-400' :
                          'bg-amber-500/10 text-amber-400'
                        }`}>
                          {evt.event_type}
                        </span>
                      </td>
                      <td className="p-3 text-slate-400">{evt.decision_id || '-'}</td>
                      <td className="p-3 text-slate-400">{evt.timestamp}</td>
                      <td className="p-3 max-w-xs truncate text-slate-300">
                        {JSON.stringify(evt.payload)}
                      </td>
                      <td className="p-3 text-slate-500 max-w-xs truncate" title={evt.record_hash}>
                        {evt.record_hash?.slice(0, 16)}...
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: DEMO SCENARIOS */}
        {activeTab === 'scenarios' && (
          <div className="space-y-4 max-w-5xl mx-auto">
            <div className="pb-2">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Automated Demo Scenarios (1–15)</h2>
              <p className="text-xs text-slate-400">Trigger standard calibration, edge-case, and attacker injection scenarios directly</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { id: 1, title: '1. Standard Allowed Reads', desc: 'database-agent reads orders, analytics reads sales -> Score 20, ALLOW.' },
                { id: 2, title: '2. High-Value Finance Review', desc: 'finance creates payment 85000 off-hours -> Score 65, REVIEW -> Approver approves -> Executes once.' },
                { id: 3, title: '3. Destructive PII Deletion Block', desc: 'database-agent attempts DELETE on customers_prod -> Score 100, BLOCK (PERM-001 & DATA-004).' },
                { id: 4, title: '4. Prompt Injection Defense', desc: 'external_content attempts DELETE on staging_db -> Hard BLOCK (INJ-002).' },
                { id: 5, title: '5. External Content Refund', desc: 'email refund 9000 (Score 50, REVIEW) vs 90000 (Score 70, BLOCK).' },
                { id: 6, title: '6. Split Refund Rapid Velocity', desc: 'Five 9500 payments allowed (47500 total), 6th payment blocked by cumulative velocity gate.' },
                { id: 7, title: '7. Tampered Approval Attack', desc: 'Approval for 85000 resubmitted as 850000 -> 403 BLOCK, approval VOIDED (hash_mismatch).' },
                { id: 8, title: '8. Consumed Approval Replay', desc: 'Replay already consumed approval -> 403 BLOCK (replay_attempt).' },
                { id: 9, title: '9. Lying Agent Context Resolution', desc: 'database-agent claims dev/public -> Resolved context production/PII wins (I3).' },
                { id: 10, title: '10. Fail-Closed Resilience', desc: 'Offline Guard causes Gateway to fail closed with 503 denied_fail_closed.' },
                { id: 11, title: '11. Audit Tamper Detection', desc: 'Alters audit record via direct SQL -> verify reports valid=false -> reset restores.' },
                { id: 12, title: '12. Direct Tool Credential Access', desc: 'Calls mock tool without TOOL_CREDENTIAL -> PermissionError raised.' },
                { id: 13, title: '13. Unknown Target Governance', desc: 'READ mystery_db -> REVIEW (score 40 floor); DELETE mystery_db -> BLOCK (REG-003).' },
                { id: 14, title: '14. Role & Actor Abuse Defense', desc: 'Agent calling /decide or Actor header mismatch -> 403 forbidden.' },
                { id: 15, title: '15. Admin Kill Switch', desc: 'Admin sets agent inactive -> immediate hard BLOCK (AGT-001).' },
              ].map((sc) => (
                <div key={sc.id} className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-emerald-400">{sc.title}</span>
                    <button
                      onClick={() => handleRunScenario(sc.id)}
                      disabled={runningScenario === sc.id}
                      className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white text-xs font-semibold rounded-lg flex items-center space-x-1"
                    >
                      <Play className="w-3 h-3" />
                      <span>{runningScenario === sc.id ? 'Running...' : 'Run Scenario'}</span>
                    </button>
                  </div>
                  <p className="text-xs text-slate-400">{sc.desc}</p>

                  {/* Scenario Output */}
                  {scenarioResults[sc.id] && (
                    <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                      <span className="text-[10px] font-mono text-slate-500 uppercase block mb-1">Result:</span>
                      <pre className="text-[11px] font-mono text-slate-300 overflow-x-auto max-h-32">
                        {JSON.stringify(scenarioResults[sc.id], null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: AGENTS & REGISTRIES */}
        {activeTab === 'registries' && (
          <div className="space-y-6 max-w-5xl mx-auto">
            {/* Policy Version & Kill Switch */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 flex items-center justify-between">
              <div>
                <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Active Policy Version (SHA-256):</span>
                <p className="font-mono text-emerald-400 text-xs mt-0.5">{policyVersion || 'Loading...'}</p>
              </div>
              <span className="text-xs px-2.5 py-1 bg-slate-800 text-slate-400 rounded">
                Tamper-Evident Policy Hash
              </span>
            </div>

            {/* Agent Registry */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Agent Registry & Admin Kill-Switch</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(agents).map(([agentId, ag]) => (
                  <div key={agentId} className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-slate-200">{agentId}</span>
                        <p className="text-xs text-slate-400">Department: {ag.department}</p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          ag.status === 'active' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                        }`}>
                          {ag.status}
                        </span>
                        <button
                          onClick={() => toggleAgentStatus(agentId, ag.status)}
                          className={`p-1.5 rounded-lg text-xs font-semibold ${
                            ag.status === 'active' ? 'bg-rose-900/40 hover:bg-rose-900 text-rose-300' : 'bg-emerald-900/40 hover:bg-emerald-900 text-emerald-300'
                          }`}
                          title="Toggle Status (Admin Kill Switch)"
                        >
                          <Power className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="text-xs space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase font-mono">Explicit Permissions:</span>
                      <ul className="space-y-0.5">
                        {ag.permissions?.map((p, idx) => (
                          <li key={idx} className="font-mono text-[11px] text-slate-400">
                            • <strong className="text-slate-200">{p.action}</strong> on <span className="text-emerald-400">{p.target_pattern}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Resource Registry */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Resource Registry & Classifications</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(resources).map(([target, res]) => (
                  <div key={target} className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/30 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-200">{target}</span>
                      <span className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] uppercase font-mono">
                        {res.environment}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-slate-400 text-[11px]">
                      <div>Data Class: <strong className="text-amber-400">{res.data_class}</strong></div>
                      <div>Records: <strong className="text-slate-200">{res.record_count.toLocaleString()}</strong></div>
                      <div>Reversible: <strong className={res.reversible ? 'text-emerald-400' : 'text-rose-400'}>{res.reversible ? 'Yes' : 'No'}</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
