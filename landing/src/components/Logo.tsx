import React from 'react';

interface LogoProps {
  size?: number;
  className?: string;
  showWordmark?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ size = 28, className = '', showWordmark = false }) => {
  return (
    <div className={`inline-flex items-center gap-3 select-none ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={`bgGrad-${size}`} x1="12" y1="10" x2="88" y2="90" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#7C5CF5" />
            <stop offset="100%" stopColor="#5522E0" />
          </linearGradient>
          <linearGradient id={`innerGlow-${size}`} x1="20" y1="20" x2="80" y2="80" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#9E86FF" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#4314B5" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        {/* Shield contour */}
        <path
          d="M50 8C68 18 84 21 84 46C84 70 65 86 50 92C35 86 16 70 16 46C16 21 32 18 50 8Z"
          fill={`url(#bgGrad-${size})`}
        />
        {/* Soft bevel inner ring */}
        <path
          d="M50 18C63 26 74 29 74 47C74 65 59 78 50 82C41 78 26 65 26 47C26 29 37 26 50 18Z"
          fill={`url(#innerGlow-${size})`}
          opacity="0.4"
        />
        {/* Authoritative Gateway Keyhole */}
        <path
          d="M50 32C44.4772 32 40 36.4772 40 42C40 46.2229 42.6175 49.8329 46.3333 51.25V63C46.3333 65.0251 47.9749 66.6667 50 66.6667C52.0251 66.6667 53.6667 65.0251 53.6667 63V51.25C57.3825 49.8329 60 46.2229 60 42C60 36.4772 55.5228 32 50 32ZM50 38C52.2091 38 54 39.7909 54 42C54 44.2091 52.2091 46 50 46C47.7909 46 46 44.2091 46 42C46 39.7909 47.7909 38 50 38Z"
          fill="#FFFFFF"
        />
        <circle cx="50" cy="42" r="2.5" fill="#A78BFA" />
      </svg>
      {showWordmark && (
        <span className="font-bold text-[15px] tracking-[0.22em] text-ink uppercase">
          AGENTGUARD
        </span>
      )}
    </div>
  );
};
