'use client';

import { useRef, useCallback, ReactNode } from 'react';

interface MagneticButtonProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  as?: 'button' | 'a';
  href?: string;
}

export function MagneticButton({ children, className = '', onClick, as = 'button', href }: MagneticButtonProps) {
  const ref = useRef<HTMLElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);

  const handleMove = useCallback((e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const maxDist = 60;
    if (dist < maxDist) {
      const f = (1 - dist / maxDist) * 12;
      const tx = (dx / dist) * f || 0;
      const ty = (dy / dist) * f || 0;
      el.style.transform = `translate(${tx}px, ${ty}px)`;
      if (textRef.current) {
        textRef.current.style.transform = `translate(${tx * 0.5}px, ${ty * 0.5}px)`;
      }
    }
  }, []);

  const handleLeave = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = '';
    if (textRef.current) textRef.current.style.transform = '';
  }, []);

  const Tag = as as any;

  return (
    <Tag
      ref={ref}
      className={`transition-transform duration-300 ${className}`}
      style={{ willChange: 'transform' }}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      onClick={onClick}
      href={href}
    >
      <span ref={textRef} className="inline-flex items-center gap-2 transition-transform duration-200">
        {children}
      </span>
    </Tag>
  );
}
