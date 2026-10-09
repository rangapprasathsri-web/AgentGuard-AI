import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { ProductShowcase } from './components/ProductShowcase';
import { Problem } from './components/Problem';
import { BentoGrid } from './components/BentoGrid';
import { HowItWorks } from './components/HowItWorks';
import { InteractiveDemo } from './components/InteractiveDemo';
import { FinalCta } from './components/FinalCta';
import { Footer } from './components/Footer';
import { AuthPage } from './pages/AuthPage';

const THEME_STORAGE_KEY = 'agentguard-theme';

const LandingContent: React.FC = () => {
  const [currentView, setCurrentView] = useState<'landing' | 'auth'>(() => {
    return window.location.pathname.startsWith('/auth') ||
      new URLSearchParams(window.location.search).get('view') === 'auth'
      ? 'auth'
      : 'landing';
  });

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const queryTheme = urlParams.get('theme');
      if (queryTheme === 'dark' || queryTheme === 'light') return queryTheme;
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      if (stored === 'dark' || stored === 'light') return stored;
    } catch {
      // ignore
    }
    return 'light';
  });

  useEffect(() => {
    const handlePopState = () => {
      if (window.location.pathname.startsWith('/auth')) {
        setCurrentView('auth');
      } else {
        setCurrentView('landing');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    try {
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.colorScheme = theme;
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const navigateToAuth = () => {
    window.history.pushState({}, '', '/auth');
    setCurrentView('auth');
  };

  const navigateToLanding = () => {
    window.history.pushState({}, '', '/');
    setCurrentView('landing');
  };

  if (currentView === 'auth') {
    return <AuthPage onBackToHome={navigateToLanding} />;
  }

  return (
    <div className="min-h-screen bg-page text-ink selection:bg-brand-soft selection:text-brand-ink transition-colors duration-200">
      {/* 1. NAVBAR */}
      <Navbar
        theme={theme}
        toggleTheme={toggleTheme}
        onOpenAuth={navigateToAuth}
      />

      <main>
        {/* 2. HERO */}
        <Hero />

        {/* 3. PRODUCT SHOWCASE */}
        <ProductShowcase />

        {/* 4. THE PROBLEM */}
        <Problem />

        {/* 5. WHAT AGENTGUARD DOES (Bento Grid) */}
        <BentoGrid />

        {/* 6. HOW IT WORKS */}
        <HowItWorks />

        {/* 7. INTERACTIVE DEMO */}
        <InteractiveDemo />

        {/* 8. FINAL CTA */}
        <FinalCta />
      </main>

      {/* 9. FOOTER */}
      <Footer />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <LandingContent />
    </AuthProvider>
  );
};

export default App;

