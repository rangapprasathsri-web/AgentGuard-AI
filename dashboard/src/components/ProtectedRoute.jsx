import React from 'react';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute = ({ children, onRequireAuth }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 gap-3">
        <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
        <span className="text-sm font-medium">Verifying owner credentials...</span>
      </div>
    );
  }

  if (!user) {
    if (onRequireAuth) {
      onRequireAuth();
      return null;
    }
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-center">
        <div className="max-w-md w-full p-8 rounded-2xl bg-slate-900 border border-slate-800 text-slate-300">
          <h2 className="text-xl font-bold text-white mb-2">Authentication Required</h2>
          <p className="text-sm text-slate-400 mb-6">
            Sign in as the website owner to access the AgentGuard governance dashboard.
          </p>
          <a
            href="/auth"
            className="inline-flex items-center justify-center w-full h-11 rounded-full bg-indigo-600 text-white font-medium hover:bg-indigo-500 transition-colors"
          >
            Go to Sign in
          </a>
        </div>
      </div>
    );
  }

  return children;
};
