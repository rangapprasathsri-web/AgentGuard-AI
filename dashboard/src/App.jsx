import React, { useState, useEffect } from 'react';
import { 
  Shield, AlertTriangle, CheckCircle, XCircle, Clock, 
  Terminal, Database, Lock, RefreshCw, FileText, UserCheck, 
  Layers, ChevronRight, AlertOctagon, Cpu, Hash, Play,
  Search, ShieldAlert, Check, X, Eye, EyeOff, ExternalLink, Power, Info,
  Key, Copy, LogOut, Globe, Plus, Building2, User
} from 'lucide-react';
import { useAuth } from './context/AuthContext';
import AuthPage from './pages/AuthPage';

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

export default function App() {
  const { user, loading, signOut, getIdToken } = useAuth();

  const [activeTab, setActiveTab] = useState('feed');
  const [currentRole, setCurrentRole] = useState('approver');
  const [currentActor, setCurrentActor] = useState('approver_cfo');
  
  // Owner Tenant states
  const [tenants, setTenants] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [tenantsLoading, setTenantsLoading] = useState(true);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [registeringTenant, setRegisteringTenant] = useState(false);
  const [registerError, setRegisterError] = useState(null);
  const [credentialsModal, setCredentialsModal] = useState(null);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [rotatingKey, setRotatingKey] = useState(false);
  const [rotatedKeyModal, setRotatedKeyModal] = useState(null);
  const [tenantLimits, setTenantLimits] = useState(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);

  // Approver Login states (Separate token authentication)
  const [approverToken, setApproverToken] = useState('');
  const [approverInput, setApproverInput] = useState('');
  const [approverError, setApproverError] = useState('');

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

  // Fetch Owner Tenants when user signs in
  useEffect(() => {
    if (user) {
      loadTenants();
    } else {
      setTenants([]);
      setSelectedTenant(null);
      setTenantsLoading(false);
    }
  }, [user]);

  // Load limits whenever selected tenant changes
  useEffect(() => {
    if (selectedTenant) {
      loadTenantLimits(selectedTenant.id || selectedTenant.tenant_id);
    }
  }, [selectedTenant]);

  const loadTenants = async () => {
    try {
      setTenantsLoading(true);
      const token = await getIdToken();
      if (!token) return;
      const res = await fetch(`${GUARD_API}/tenants/mine`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const list = await res.json();
        setTenants(list);
        if (list.length > 0) {
          setSelectedTenant(prev => {
            if (!prev) return list[0];
            const match = list.find(t => (t.id || t.tenant_id) === (prev.id || prev.tenant_id));
            return match || list[0];
          });
        } else {
          setSelectedTenant(null);
        }
      }
    } catch (e) {
      console.error('Failed to load owner tenants:', e);
    } finally {
      setTenantsLoading(false);
    }
  };

  const loadTenantLimits = async (tenantId) => {
    try {
      const token = await getIdToken();
      if (!token || !tenantId) return;
      const res = await fetch(`${GUARD_API}/tenants/${tenantId}/limits`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setTenantLimits(await res.json());
      }
    } catch (e) {
      console.warn('Failed to load limits:', e);
    }
  };

  // Auto-poll data every 2 seconds when user is authenticated
  useEffect(() => {
    if (!user) return;
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [user, currentRole, currentActor, selectedTenant]);

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
      // Backend offline or reconnecting
    }
  };

  // Connect / Register new tenant
  const handleRegisterTenant = async (e) => {
    if (e) e.preventDefault();
    if (!newCompanyName.trim()) return;
    setRegisteringTenant(true);
    setRegisterError(null);
    try {
      const token = await getIdToken();
      const res = await fetch(`${GUARD_API}/tenants/register`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ company: newCompanyName.trim() })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to register website tenant');
      }
      const data = await res.json();
      setCredentialsModal(data);
      setNewCompanyName('');
      setShowConnectModal(false);
      await loadTenants();
    } catch (err) {
      setRegisterError(err.message);
    } finally {
      setRegisteringTenant(false);
    }
  };

  // Rotate Key for active tenant
  const handleRotateKey = async () => {
    if (!selectedTenant) return;
    const tenantId = selectedTenant.id || selectedTenant.tenant_id;
    if (!window.confirm(`Rotate API key for ${selectedTenant.company}? Existing active keys will be permanently revoked.`)) {
      return;
    }
    setRotatingKey(true);
    try {
      const token = await getIdToken();
      const res = await fetch(`${GUARD_API}/tenants/${tenantId}/rotate-key`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Rotation failed');
      }
      const data = await res.json();
      setRotatedKeyModal(data);
    } catch (err) {
      alert('Error rotating key: ' + err.message);
    } finally {
      setRotatingKey(false);
    }
  };

  // Approver Decisions (requires Approver Token)
  const handleApprove = async (id) => {
    if (!approverToken) {
      alert('Approval requires an authenticated Approver Token. Please login as an Approver below.');
      return;
    }
    try {
      const res = await fetch(`${GUARD_API}/approvals/${id}/decide`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${approverToken.trim()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ decision: 'APPROVE', reason: 'Approved by human approver via Governance UI' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Approval rejected');
      }
      fetchData();
    } catch (e) {
      alert('Approval failed: ' + e.message);
    }
  };

  const handleReject = async (id) => {
    if (!approverToken) {
      alert('Rejection requires an authenticated Approver Token. Please login as an Approver below.');
      return;
    }
    try {
      const res = await fetch(`${GUARD_API}/approvals/${id}/decide`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${approverToken.trim()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ decision: 'REJECT', reason: rejectReason || 'Rejected by human approver' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Rejection failed');
      }
      setRejectingId(null);
      setRejectReason('');
      fetchData();
    } catch (e) {
      alert('Rejection failed: ' + e.message);
    }
  };

  // Clear in-memory state on Sign Out
  const handleSignOut = async () => {
    await signOut();
    setDecisions([]);
    setApprovals([]);
    setAuditEvents([]);
    setTenants([]);
    setSelectedTenant(null);
    setTenantLimits(null);
    setApproverToken('');
    setCredentialsModal(null);
    setRotatedKeyModal(null);
  };

  const toggleAgentStatus = async (agentId, currentStatus) => {
    if (currentRole !== 'admin') {
      alert('Kill switch requires ADMIN role!');
      return;
    }
    const newStatus = currentStatus === 'ACTIVE' ? 'KILLED' : 'ACTIVE';
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

  const runScenario = async (id) => {
    setRunningScenario(id);
    try {
      const res = await fetch(`${DEMO_API}/demo/run/${id}`, { method: 'POST' });
      const data = await res.json();
      setScenarioResults((prev) => ({ ...prev, [id]: data }));
      fetchData();
    } catch (e) {
      alert(`Scenario ${id} execution failed: ` + e.message);
    } finally {
      setRunningScenario(null);
    }
  };

  const triggerTamper = async () => {
    if (currentRole !== 'admin') {
      alert('Tamper demonstration requires ADMIN role!');
      return;
    }
    setTampering(true);
    try {
      await fetch(`${GUARD_API}/audit/demo/tamper`, { method: 'POST', headers: getHeaders() });
      await fetchData();
    } catch (e) {
      alert('Tamper injection failed: ' + e.message);
    } finally {
      setTampering(false);
    }
  };

  const triggerReset = async () => {
    if (currentRole !== 'admin') {
      alert('Reset requires ADMIN role!');
      return;
    }
    setResetting(true);
    try {
      await fetch(`${GUARD_API}/demo/reset`, { method: 'POST', headers: getHeaders() });
      setScenarioResults({});
      await fetchData();
    } catch (e) {
      alert('Reset failed: ' + e.message);
    } finally {
      setResetting(false);
    }
  };

  const getDecisionBadge = (decision) => {
    if (decision === 'ALLOW') return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">ALLOW</span>;
    if (decision === 'REVIEW') return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">REVIEW</span>;
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">BLOCK</span>;
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#090d16] flex flex-col items-center justify-center text-slate-300">
        <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin mb-3" />
        <p className="text-sm font-medium">Verifying owner session...</p>
      </div>
    );
  }

  // Signed-out state
  if (!user) {
    return <AuthPage />;
  }

  const providerName = user.providerData?.[0]?.providerId === 'google.com' ? 'Google' : 'Password';

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
                Owner Dashboard
              </span>
            </div>
            <p className="text-xs text-slate-400">Execution Authorization & Governance Layer</p>
          </div>
        </div>

        {/* Global Security Badges, Tenant Picker & User Profile */}
        <div className="flex items-center space-x-3">
          {/* Tenant Picker */}
          {tenants.length > 0 && (
            <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-xs">
              <Building2 className="w-3.5 h-3.5 text-emerald-400" />
              <select
                value={selectedTenant ? (selectedTenant.id || selectedTenant.tenant_id) : ''}
                onChange={(e) => {
                  const match = tenants.find(t => (t.id || t.tenant_id) === e.target.value);
                  if (match) setSelectedTenant(match);
                }}
                className="bg-transparent text-slate-200 font-semibold focus:outline-none cursor-pointer"
              >
                {tenants.map((t) => (
                  <option key={t.id || t.tenant_id} value={t.id || t.tenant_id} className="bg-slate-900 text-slate-200">
                    {t.company} ({t.id || t.tenant_id})
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowConnectModal(true)}
                title="Connect another website"
                className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-emerald-400 transition"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Audit Chain Status */}
          <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs">
            <span className="text-slate-400 font-medium flex items-center">
              Audit Chain:
            </span>
            {auditVerify.valid ? (
              <span className="flex items-center text-emerald-400 font-semibold space-x-1">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>INTACT</span>
              </span>
            ) : (
              <span className="flex items-center text-rose-400 font-semibold space-x-1 animate-pulse">
                <AlertOctagon className="w-3.5 h-3.5" />
                <span>BROKEN</span>
              </span>
            )}
          </div>

          {/* User Profile Pill */}
          <div className="flex items-center space-x-2 pl-2 border-l border-slate-800">
            <div className="flex flex-col text-right">
              <span className="text-xs font-semibold text-slate-200 truncate max-w-[150px]">{user.email}</span>
              <span className="text-[10px] text-emerald-400 font-mono flex items-center justify-end">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1"></span>
                {providerName}
              </span>
            </div>
            <button
              onClick={handleSignOut}
              title="Sign Out"
              className="p-1.5 rounded-lg bg-slate-900 hover:bg-rose-950/60 border border-slate-800 hover:border-rose-800 text-slate-400 hover:text-rose-300 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Tenant Management Sub-Header (When tenant exists) */}
      {selectedTenant && (
        <div className="bg-slate-900/60 border-b border-slate-800 px-6 py-2.5 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <span className="text-slate-400">Connected Website:</span>
              <strong className="text-slate-100 font-medium">{selectedTenant.company}</strong>
              <span className="font-mono text-[11px] text-slate-500 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/50">
                {selectedTenant.id || selectedTenant.tenant_id}
              </span>
            </div>

            {/* Tenant Limits Info */}
            <div className="hidden md:flex items-center space-x-3 text-slate-400 border-l border-slate-800 pl-4 text-[11px]">
              <span>Max Refund: <strong className="text-emerald-400">₹{(tenantLimits?.max_single_refund || 50000).toLocaleString('en-IN')}</strong></span>
              <span>Daily Cap: <strong className="text-emerald-400">₹{(tenantLimits?.daily_cumulative_cap || 200000).toLocaleString('en-IN')}</strong></span>
              <span>Review: <strong className="text-amber-400">₹{(tenantLimits?.payment_review_threshold || 10000).toLocaleString('en-IN')}</strong></span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleRotateKey}
              disabled={rotatingKey}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 flex items-center space-x-1 font-medium transition"
            >
              <RefreshCw className={`w-3 h-3 ${rotatingKey ? 'animate-spin' : ''}`} />
              <span>Rotate API Key</span>
            </button>
          </div>
        </div>
      )}

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

        {/* Policy Version */}
        <div className="text-[11px] font-mono text-slate-500">
          Policy: <span className="text-slate-300">{policyVersion || 'v1.0.0-invariants'}</span>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">

        {/* ONBOARDING: NO TENANT CONNECTED YET */}
        {tenants.length === 0 && !tenantsLoading && (
          <div className="max-w-xl mx-auto my-12 bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mb-5 text-emerald-400">
              <Globe className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Connect Your Website</h2>
            <p className="text-xs text-slate-400 mb-6 leading-relaxed">
              Welcome to AgentGuard AI! You do not have any registered websites yet. 
              Register your website name below to receive your one-time live API key and human approver credentials.
            </p>

            <form onSubmit={handleRegisterTenant} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Company or Website Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Acme Commerce"
                  value={newCompanyName}
                  onChange={(e) => setNewCompanyName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition"
                />
              </div>

              {registerError && (
                <div className="p-3 bg-rose-950/40 border border-rose-800 rounded-lg text-xs text-rose-300">
                  {registerError}
                </div>
              )}

              <button
                type="submit"
                disabled={registeringTenant}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-semibold text-xs transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20"
              >
                {registeringTenant ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Key className="w-4 h-4" />
                    <span>Generate API Key & Connect</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* TAB 1: DECISIONS FEED */}
        {activeTab === 'feed' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div className="flex items-center space-x-2">
                  <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                    Evaluated Actions Feed
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
                      <p className="font-mono text-slate-300 break-all text-[11px] mt-0.5">{selectedDecision.decision_id}</p>
                      <p className="font-mono text-slate-500 break-all text-[10px] mt-0.5">Hash: {selectedDecision.action_hash}</p>
                    </div>

                    <div>
                      <span className="text-slate-500 font-medium uppercase text-[10px] tracking-wider">Evaluation Source</span>
                      <p className="text-slate-200 font-semibold mt-0.5 flex items-center">
                        <Terminal className="w-3.5 h-3.5 mr-1 text-emerald-400" />
                        {selectedDecision.decision_source}
                      </p>
                    </div>

                    {selectedDecision.response && (
                      <div className="space-y-3">
                        {selectedDecision.response.reasons && (
                          <div>
                            <span className="text-slate-500 font-medium uppercase text-[10px] tracking-wider">Primary Reasons</span>
                            <ul className="list-disc list-inside text-slate-300 mt-1 space-y-1">
                              {selectedDecision.response.reasons.map((r, i) => (
                                <li key={i}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {selectedDecision.response.risk_factors && (
                          <div>
                            <span className="text-slate-500 font-medium uppercase text-[10px] tracking-wider">Risk Factors</span>
                            <div className="flex flex-wrap gap-1.5 mt-1.5">
                              {selectedDecision.response.risk_factors.map((rf, i) => (
                                <span key={i} className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[11px] font-mono">
                                  {rf}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: APPROVAL QUEUE (With Separate Human Approver Authentication) */}
        {activeTab === 'approvals' && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div>
                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center">
                  Human-in-the-Loop Approval Queue
                  <InfoTooltip text="Actions scoring above the safety threshold require explicit human approval. Per AgentGuard AI invariant rules, website owners do not inherit approval authority automatically." />
                </h2>
                <p className="text-xs text-slate-400">Strict one-time approval token authorization</p>
              </div>

              {approverToken && (
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] text-emerald-400 font-mono bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-1 rounded-md flex items-center space-x-1">
                    <UserCheck className="w-3.5 h-3.5" />
                    <span>Approver Active</span>
                  </span>
                  <button
                    onClick={() => setApproverToken('')}
                    className="text-xs text-slate-400 hover:text-slate-200 underline"
                  >
                    Disconnect Token
                  </button>
                </div>
              )}
            </div>

            {/* Approver Login Panel */}
            {!approverToken && (
              <div className="p-5 rounded-xl border border-amber-500/30 bg-amber-950/10 backdrop-blur space-y-3">
                <div className="flex items-start space-x-3">
                  <Lock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-sm font-bold text-amber-300">Approver Authentication Required</h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      To approve or reject high-risk actions, enter your human approver token. 
                      Agents and website owners cannot authorize their own requests.
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 pt-2">
                  <input
                    type="password"
                    placeholder="Enter Approver Token (from website registration)"
                    value={approverInput}
                    onChange={(e) => setApproverInput(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
                  />
                  <button
                    onClick={() => {
                      if (!approverInput.trim()) return;
                      setApproverToken(approverInput.trim());
                      setApproverInput('');
                    }}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow transition"
                  >
                    Authenticate Approver
                  </button>
                </div>
              </div>
            )}

            {/* Approvals Listing */}
            {approvals.length === 0 ? (
              <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
                No active approvals in queue. Trigger a high-risk scenario to test human authorization.
              </div>
            ) : (
              <div className="space-y-4">
                {approvals.map((appr) => (
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
                          Requested by <strong className="text-slate-200">{appr.agent_id}</strong> • Expires: {appr.expires_at}
                        </p>
                      </div>

                      {appr.status === 'PENDING' && (
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => handleApprove(appr.id)}
                            className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1 shadow transition"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Approve</span>
                          </button>
                          <button
                            onClick={() => setRejectingId(rejectingId === appr.id ? null : appr.id)}
                            className="px-3.5 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white rounded-lg text-xs font-semibold flex items-center space-x-1 transition"
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Reject</span>
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="p-3 bg-slate-950/80 border border-slate-800/80 rounded-lg">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                        Bound Action Parameters:
                      </span>
                      <pre className="text-xs font-mono text-emerald-400 overflow-x-auto">
                        {JSON.stringify(appr.canonical_action, null, 2)}
                      </pre>
                    </div>

                    {rejectingId === appr.id && (
                      <div className="p-3 bg-rose-950/20 border border-rose-800/40 rounded-lg space-y-2">
                        <label className="text-xs text-rose-300 font-medium">Rejection Reason:</label>
                        <input
                          type="text"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="Reason for rejection..."
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

        {/* TAB 3: AUDIT LOG & TAMPER CHAIN */}
        {activeTab === 'audit' && (
          <div className="space-y-4 max-w-6xl mx-auto">
            <div className="flex items-center justify-between pb-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center">
                  Tamper-Evident HMAC Hash Chain Audit Log
                  <InfoTooltip text="Each log record contains the cryptographic HMAC of the previous record. This makes unauthorized alteration or deletion computationally impossible." />
                </h2>
                <p className="text-xs text-slate-400">Append-only HMAC-SHA256 linked records</p>
              </div>

              {/* Tamper / Reset Controls (Demo Mode) */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={triggerTamper}
                  disabled={tampering}
                  className="px-3 py-1.5 bg-rose-950 hover:bg-rose-900 border border-rose-700/60 text-rose-300 rounded-lg text-xs font-semibold transition"
                >
                  Inject Tamper
                </button>
                <button
                  onClick={triggerReset}
                  disabled={resetting}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
                >
                  Reset Ledger
                </button>
              </div>
            </div>

            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/40">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 text-slate-400 font-mono text-[11px] border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Seq</th>
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Record Hash</th>
                      <th className="py-2.5 px-3">Payload Summary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {auditEvents.map((evt) => (
                      <tr key={evt.id || evt.seq} className="hover:bg-slate-800/30">
                        <td className="py-2 px-3 text-slate-400">{evt.seq}</td>
                        <td className="py-2 px-3 text-slate-500 truncate max-w-[150px]">{evt.timestamp}</td>
                        <td className="py-2 px-3 font-semibold text-emerald-400">{evt.event_type}</td>
                        <td className="py-2 px-3 text-slate-500 truncate max-w-[120px]">{evt.record_hash}</td>
                        <td className="py-2 px-3 text-slate-300 truncate max-w-[300px]">{typeof evt.payload === 'string' ? evt.payload : JSON.stringify(evt.payload)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: DEMO SCENARIOS */}
        {activeTab === 'scenarios' && (
          <div className="space-y-4 max-w-6xl mx-auto">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Automated Governance Test Scenarios</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { id: '1', title: 'Scenario 1: Low-Risk Read (Auto ALLOW)' },
                { id: '2', title: 'Scenario 2: Single Refund Limit Exceeded (BLOCK)' },
                { id: '3', title: 'Scenario 3: 24h Cumulative Cap Exceeded (BLOCK)' },
                { id: '4', title: 'Scenario 4: High-Risk Action (Enters REVIEW)' },
                { id: '5', title: 'Scenario 5: Parameter Tampering on Approval (BLOCK)' },
                { id: '6', title: 'Scenario 6: Prompt Injection Defense (BLOCK)' },
              ].map((sc) => (
                <div key={sc.id} className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
                  <h4 className="text-xs font-bold text-slate-200">{sc.title}</h4>
                  <button
                    onClick={() => runScenario(sc.id)}
                    disabled={runningScenario === sc.id}
                    className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-emerald-400 rounded text-xs font-semibold transition"
                  >
                    {runningScenario === sc.id ? 'Running...' : 'Run Scenario'}
                  </button>
                  {scenarioResults[sc.id] && (
                    <pre className="text-[10px] font-mono text-slate-400 bg-slate-950 p-2 rounded max-h-24 overflow-y-auto">
                      {JSON.stringify(scenarioResults[sc.id], null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: REGISTRIES */}
        {activeTab === 'registries' && (
          <div className="space-y-6 max-w-6xl mx-auto">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Agents & Policies Registry</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(agents).map(([agentId, ag]) => (
                <div key={agentId} className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-slate-200">{ag.name} ({agentId})</span>
                    <button
                      onClick={() => toggleAgentStatus(agentId, ag.status)}
                      className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                        ag.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                      }`}
                    >
                      {ag.status} (Toggle Kill Switch)
                    </button>
                  </div>
                  <p className="text-xs text-slate-400">Department: {ag.department} • Tier: {ag.risk_tier}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* CREDENTIALS MODAL (Shown once upon registration) */}
      {credentialsModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center space-x-3 text-emerald-400">
              <CheckCircle className="w-6 h-6" />
              <h3 className="text-lg font-bold text-white">Website Connected Successfully</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your website credentials have been generated. Copy and securely store your live API key now. 
              For security, this key is never shown again.
            </p>

            <div className="space-y-3 font-mono text-xs">
              <div>
                <label className="text-[10px] font-sans font-semibold text-slate-400 uppercase">Tenant ID</label>
                <div className="bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-slate-200 select-all">
                  {credentialsModal.tenant_id}
                </div>
              </div>

              <div>
                <label className="text-[10px] font-sans font-semibold text-amber-400 uppercase flex items-center justify-between">
                  <span>Live API Key (ag_live_...)</span>
                  <span className="text-[10px] text-rose-400 font-normal">Shown Once Only</span>
                </label>
                <div className="bg-slate-950 border border-amber-500/50 p-2.5 rounded-lg text-amber-300 flex items-center justify-between">
                  <span className="truncate mr-2">{credentialsModal.api_key}</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(credentialsModal.api_key);
                      setCopiedKey(true);
                      setTimeout(() => setCopiedKey(false), 2000);
                    }}
                    className="p-1.5 hover:bg-slate-800 rounded text-slate-300 hover:text-white transition shrink-0"
                  >
                    {copiedKey ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-sans font-semibold text-slate-400 uppercase">Approver Token (Human Authorization)</label>
                <div className="bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-slate-300 flex items-center justify-between">
                  <span className="truncate mr-2">{credentialsModal.approver_token}</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(credentialsModal.approver_token);
                      setCopiedToken(true);
                      setTimeout(() => setCopiedToken(false), 2000);
                    }}
                    className="p-1.5 hover:bg-slate-800 rounded text-slate-300 hover:text-white transition shrink-0"
                  >
                    {copiedToken ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-sans font-semibold text-slate-400 uppercase">Gateway URL</label>
                <div className="bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-slate-400 select-all">
                  {credentialsModal.gateway_url || 'http://localhost:8002'}
                </div>
              </div>
            </div>

            <button
              onClick={() => setCredentialsModal(null)}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition shadow-lg"
            >
              I have stored my credentials securely
            </button>
          </div>
        </div>
      )}

      {/* ROTATED KEY MODAL (Shown once upon key rotation) */}
      {rotatedKeyModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center space-x-3 text-amber-400">
              <RefreshCw className="w-6 h-6" />
              <h3 className="text-lg font-bold text-white">API Key Successfully Rotated</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your previous key has been revoked. Copy and configure your new live API key immediately.
            </p>

            <div className="space-y-3 font-mono text-xs">
              <div>
                <label className="text-[10px] font-sans font-semibold text-amber-400 uppercase flex items-center justify-between">
                  <span>New Live API Key</span>
                  <span className="text-[10px] text-rose-400 font-normal">Shown Once Only</span>
                </label>
                <div className="bg-slate-950 border border-amber-500/50 p-2.5 rounded-lg text-amber-300 flex items-center justify-between">
                  <span className="truncate mr-2">{rotatedKeyModal.api_key}</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(rotatedKeyModal.api_key);
                      setCopiedKey(true);
                      setTimeout(() => setCopiedKey(false), 2000);
                    }}
                    className="p-1.5 hover:bg-slate-800 rounded text-slate-300 hover:text-white transition shrink-0"
                  >
                    {copiedKey ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            <button
              onClick={() => setRotatedKeyModal(null)}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* CONNECT NEW WEBSITE MODAL */}
      {showConnectModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Globe className="w-4 h-4 text-emerald-400" />
                <span>Connect Another Website</span>
              </h3>
              <button onClick={() => setShowConnectModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegisterTenant} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Company / Website Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Second Website"
                  value={newCompanyName}
                  onChange={(e) => setNewCompanyName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              {registerError && (
                <div className="p-2.5 bg-rose-950/40 border border-rose-800 rounded text-xs text-rose-300">
                  {registerError}
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registeringTenant}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold flex items-center space-x-1"
                >
                  {registeringTenant && <RefreshCw className="w-3 h-3 animate-spin mr-1" />}
                  <span>Register</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
