import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  auth,
  isFirebaseConfigured,
  firebaseConfigError,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  sendPasswordResetEmail,
  fbSignOut,
  onAuthStateChanged,
  mapAuthError,
} from '../lib/firebase';

const AuthContext = createContext(undefined);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }

    // Process redirect result if returning from a redirect sign-in
    getRedirectResult(auth).catch((err) => {
      console.warn('[AgentGuard Firebase] Redirect result:', err);
    });

    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signIn = async (email, pass) => {
    if (!auth) {
      return { success: false, error: firebaseConfigError || 'Firebase not configured.' };
    }
    try {
      await signInWithEmailAndPassword(auth, email.trim(), pass);
      return { success: true };
    } catch (err) {
      return { success: false, error: mapAuthError(err) };
    }
  };

  const signUp = async (email, pass) => {
    if (!auth) {
      return { success: false, error: firebaseConfigError || 'Firebase not configured.' };
    }
    try {
      const res = await createUserWithEmailAndPassword(auth, email.trim(), pass);
      if (res.user) {
        try {
          await sendEmailVerification(res.user);
        } catch (e) {
          console.warn('[AgentGuard] Verification email send error:', e);
        }
      }
      return { success: true, verificationSent: true };
    } catch (err) {
      return { success: false, error: mapAuthError(err) };
    }
  };

  const signInWithGoogle = async () => {
    if (!auth) {
      return { success: false, error: firebaseConfigError || 'Firebase not configured.' };
    }
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    try {
      await signInWithPopup(auth, provider);
      return { success: true };
    } catch (err) {
      if (err?.code === 'auth/popup-blocked') {
        try {
          await signInWithRedirect(auth, provider);
          return { success: true };
        } catch (redirectErr) {
          return { success: false, error: mapAuthError(redirectErr) };
        }
      }
      return { success: false, error: mapAuthError(err) };
    }
  };

  const signOut = async () => {
    if (auth) {
      await fbSignOut(auth);
    }
    setUser(null);
  };

  const sendReset = async (email) => {
    if (!auth) {
      return { success: false, error: firebaseConfigError || 'Firebase not configured.' };
    }
    try {
      await sendPasswordResetEmail(auth, email.trim());
      return { success: true };
    } catch (err) {
      return { success: false, error: mapAuthError(err) };
    }
  };

  const getIdToken = async () => {
    if (!auth?.currentUser) return null;
    return await auth.currentUser.getIdToken();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isConfigured: isFirebaseConfigured,
        configError: firebaseConfigError,
        signIn,
        signUp,
        signInWithGoogle,
        signOut,
        sendReset,
        getIdToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
