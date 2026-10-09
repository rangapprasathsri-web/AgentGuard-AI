import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  auth,
  isFirebaseConfigured,
  firebaseConfigError,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  sendPasswordResetEmail,
  fbSignOut,
  onAuthStateChanged,
  mapAuthError,
  type User,
} from '../lib/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isConfigured: boolean;
  configError: string | null;
  signIn: (email: string, pass: string) => Promise<{ success: boolean; error?: string }>;
  signUp: (email: string, pass: string) => Promise<{ success: boolean; error?: string; verificationSent?: boolean }>;
  signInWithGoogle: () => Promise<{ success: boolean; error?: string }>;
  signOut: () => Promise<void>;
  sendReset: (email: string) => Promise<{ success: boolean; error?: string }>;
  getIdToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signIn = async (email: string, pass: string) => {
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

  const signUp = async (email: string, pass: string) => {
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
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      if (code === 'auth/popup-blocked') {
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

  const sendReset = async (email: string) => {
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
