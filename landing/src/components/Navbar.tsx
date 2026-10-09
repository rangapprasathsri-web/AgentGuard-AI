import React, { useState, useRef, useEffect } from 'react';
import { Logo } from './Logo';
import { Moon, Sun, Menu, X, ExternalLink, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
  onOpenAuth?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ theme, toggleTheme, onOpenAuth }) => {
  const { user, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const scrollTo = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-page/80 backdrop-blur-xl transition-colors duration-200">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6">
        {/* Left: Logo Mark + Wordmark */}
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          className="flex items-center gap-2.5 transition-opacity hover:opacity-90"
          aria-label="AgentGuard Home"
        >
          <Logo size={28} showWordmark={true} />
        </a>

        {/* Center: Nav links */}
        <nav className="hidden items-center gap-9 text-sm md:flex">
          <button
            type="button"
            onClick={() => scrollTo('features')}
            className="text-ink transition-colors hover:text-brand"
          >
            Features
          </button>
          <button
            type="button"
            onClick={() => scrollTo('how')}
            className="text-ink transition-colors hover:text-brand"
          >
            How it works
          </button>
          <button
            type="button"
            onClick={() => scrollTo('problem')}
            className="text-ink transition-colors hover:text-brand"
          >
            Why AgentGuard
          </button>
          <button
            type="button"
            onClick={() => scrollTo('demo')}
            className="text-ink transition-colors hover:text-brand"
          >
            Demo
          </button>
        </nav>

        {/* Right: Theme Toggle, Sign In, Get Started */}
        <div className="flex items-center gap-5">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
            id="theme-toggle-btn"
            className="flex h-9 w-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-ink"
          >
            {theme === 'dark' ? (
              <Sun size={18} className="stroke-[1.7]" />
            ) : (
              <Moon size={18} className="stroke-[1.7]" />
            )}
          </button>

          {user ? (
            <div className="relative" ref={userMenuRef}>
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                id="user-menu-btn"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-soft text-[13px] font-bold text-brand-ink transition-transform hover:scale-105"
                aria-label="User account menu"
              >
                {user.photoURL ? (
                  <img src={user.photoURL} alt="" className="h-9 w-9 rounded-full object-cover" />
                ) : (
                  (user.displayName?.[0] || user.email?.[0] || 'U').toUpperCase()
                )}
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 top-12 w-64 rounded-2xl border border-line bg-card p-2 shadow-soft-lg z-50">
                  <div className="px-3 py-2">
                    <p className="text-xs text-muted truncate">Signed in as</p>
                    <p className="text-sm font-semibold text-ink truncate">
                      {user.displayName || user.email}
                    </p>
                    <p className="text-xs text-muted truncate">{user.email}</p>
                  </div>
                  <div className="my-1.5 h-px bg-line" />
                  <a
                    href="http://localhost:5173"
                    className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface"
                  >
                    <ExternalLink size={14} className="text-muted" />
                    Open dashboard
                  </a>
                  <button
                    type="button"
                    onClick={async () => {
                      setUserMenuOpen(false);
                      await signOut();
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-medium text-bad transition-colors hover:bg-bad-soft"
                  >
                    <LogOut size={14} />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={onOpenAuth}
                id="nav-signin-btn"
                className="hidden text-sm font-medium text-ink transition-colors hover:text-brand sm:inline-block"
              >
                Sign in
              </button>

              <button
                type="button"
                onClick={onOpenAuth}
                id="nav-getstarted-btn"
                className="hidden h-9 items-center rounded-full bg-ink px-[18px] text-sm font-medium text-page transition-colors hover:bg-black sm:flex"
              >
                Get started
              </button>
            </>
          )}

          {/* Mobile hamburger button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            id="mobile-menu-btn"
            className="flex h-9 w-9 items-center justify-center rounded-full text-ink hover:bg-surface md:hidden"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileMenuOpen && (
        <div className="border-b border-line bg-page px-6 py-4 md:hidden animate-in slide-in-from-top">
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={() => scrollTo('features')}
              className="py-2 text-left text-base font-medium text-ink hover:text-brand"
            >
              Features
            </button>
            <button
              type="button"
              onClick={() => scrollTo('how')}
              className="py-2 text-left text-base font-medium text-ink hover:text-brand"
            >
              How it works
            </button>
            <button
              type="button"
              onClick={() => scrollTo('problem')}
              className="py-2 text-left text-base font-medium text-ink hover:text-brand"
            >
              Why AgentGuard
            </button>
            <button
              type="button"
              onClick={() => scrollTo('demo')}
              className="py-2 text-left text-base font-medium text-ink hover:text-brand"
            >
              Interactive Demo
            </button>
            <div className="my-2 h-px bg-line" />
            {user ? (
              <>
                <div className="py-2 text-xs text-muted">
                  Signed in as <span className="font-semibold text-ink">{user.email}</span>
                </div>
                <a
                  href="http://localhost:5173"
                  className="flex h-11 w-full items-center justify-center rounded-full bg-brand text-sm font-medium text-white"
                >
                  Open dashboard
                </a>
                <button
                  type="button"
                  onClick={async () => {
                    setMobileMenuOpen(false);
                    await signOut();
                  }}
                  className="flex h-11 w-full items-center justify-center rounded-full border border-bad/30 text-sm font-medium text-bad"
                >
                  Sign out
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setMobileMenuOpen(false);
                  if (onOpenAuth) onOpenAuth();
                }}
                className="flex h-11 w-full items-center justify-center rounded-full bg-ink text-sm font-medium text-page"
              >
                Sign in / Get started
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
