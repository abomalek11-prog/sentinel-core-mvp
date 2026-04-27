import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        void:        '#040810',
        deep:        '#080F18',
        surface:     '#0C1828',
        border:      '#0D2033',
        'teal-dim':  '#1A4A6E',
        teal:        '#1E90B0',
        'teal-bright':'#2CA5C8',
        amber:       '#FFC44D',
        'text-primary':'#D6E8F0',
        'text-muted': '#3A6A82',
        'text-ghost': '#1E3A4A',
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'hero':  ['clamp(4rem, 12vw, 8rem)', { lineHeight: '0.95', letterSpacing: '-0.03em' }],
        'hero-sub': ['clamp(1rem, 2.5vw, 1.375rem)', { lineHeight: '1.5' }],
      },
      animation: {
        'pulse-amber': 'pulseAmber 2.5s ease-in-out infinite',
        'scan':        'scan 4s linear infinite',
        'marquee':     'marquee 30s linear infinite',
        'float':       'float 6s ease-in-out infinite',
        'blink':       'blink 1s step-end infinite',
        'glow':        'glow 3s ease-in-out infinite',
      },
      keyframes: {
        pulseAmber: {
          '0%, 100%': { opacity: '0.5' },
          '50%':      { opacity: '1' },
        },
        scan: {
          '0%':   { top: '0%', opacity: '0' },
          '5%':   { opacity: '0.6' },
          '95%':  { opacity: '0.6' },
          '100%': { top: '100%', opacity: '0' },
        },
        marquee: {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(30,144,176,0.2)' },
          '50%':      { boxShadow: '0 0 40px rgba(30,144,176,0.4), 0 0 80px rgba(30,144,176,0.1)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-gradient': 'linear-gradient(135deg, #D6E8F0 0%, #2CA5C8 50%, #FFC44D 100%)',
      },
    },
  },
  plugins: [],
};

export default config;
