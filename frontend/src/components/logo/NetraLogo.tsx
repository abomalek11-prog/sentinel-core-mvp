'use client';

interface NetraLogoProps {
  size?: number;
  variant?: 'full' | 'icon' | 'wordmark';
  animated?: boolean;
  className?: string;
}

export function NetraLogo({ size = 32, variant = 'full', animated = false, className = '' }: NetraLogoProps) {
  const iconSize = size;
  const showIcon = variant === 'full' || variant === 'icon';
  const showText = variant === 'full' || variant === 'wordmark';

  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      {showIcon && (
        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Eye shape — two mirrored bezier curves */}
          <path
            d="M4 32 C4 18, 20 8, 32 8 C44 8, 60 18, 60 32 C60 46, 44 56, 32 56 C20 56, 4 46, 4 32Z"
            stroke="#1E90B0"
            strokeWidth="1.5"
            fill="none"
          />

          {/* CPG Graph inside eye — 6 nodes with edges */}
          <g stroke="#0D2A3F" strokeWidth="0.8">
            <line x1="22" y1="28" x2="32" y2="22" />
            <line x1="32" y1="22" x2="42" y2="28" />
            <line x1="22" y1="28" x2="22" y2="38" />
            <line x1="42" y1="28" x2="42" y2="38" />
            <line x1="22" y1="38" x2="32" y2="42" />
            <line x1="32" y1="42" x2="42" y2="38" />
            <line x1="32" y1="22" x2="32" y2="32" />
            <line x1="22" y1="28" x2="32" y2="32" />
            <line x1="42" y1="28" x2="32" y2="32" />
          </g>
          <g fill="#0D2A3F">
            <circle cx="22" cy="28" r="2.5" />
            <circle cx="32" cy="22" r="2.5" />
            <circle cx="42" cy="28" r="2.5" />
            <circle cx="22" cy="38" r="2.5" />
            <circle cx="32" cy="42" r="2.5" />
            <circle cx="42" cy="38" r="2.5" />
          </g>

          {/* Iris circle */}
          <circle cx="32" cy="32" r="8" stroke="#1E90B0" strokeWidth="1" fill="none" />

          {/* Healing arc — 300° teal arc */}
          <path
            d="M 32 24 A 8 8 0 1 1 25.07 27.07"
            stroke="#1E90B0"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
          />

          {/* Amber bridge — 60° gap filled */}
          <path
            d="M 25.07 27.07 A 8 8 0 0 1 32 24"
            stroke="#FFC44D"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            className={animated ? 'animate-pulse-amber' : ''}
          />

          {/* Patch point — amber dot */}
          <circle
            cx="25.07"
            cy="27.07"
            r="3"
            fill="#FFC44D"
            className={animated ? 'animate-pulse-amber' : ''}
          />

          {/* Central node */}
          <circle cx="32" cy="32" r="2" fill="#1E90B0" />
        </svg>
      )}

      {showText && (
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 300,
            fontSize: `${size * 0.55}px`,
            letterSpacing: '0.2em',
            color: '#D6E8F0',
          }}
        >
          NETRA
        </span>
      )}
    </div>
  );
}
