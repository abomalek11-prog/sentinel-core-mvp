'use client';

import { useEffect, useRef } from 'react';

export function CustomCursor() {
  const outerRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const pos      = useRef({ x: 0, y: 0 });
  const outer    = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      pos.current = { x: e.clientX, y: e.clientY };
      if (innerRef.current) {
        innerRef.current.style.left = `${e.clientX}px`;
        innerRef.current.style.top  = `${e.clientY}px`;
      }
    };

    const onEnter = () => outerRef.current?.classList.add('hovering');
    const onLeave = () => outerRef.current?.classList.remove('hovering');

    const animate = () => {
      outer.current.x += (pos.current.x - outer.current.x) * 0.15;
      outer.current.y += (pos.current.y - outer.current.y) * 0.15;
      if (outerRef.current) {
        outerRef.current.style.left = `${outer.current.x}px`;
        outerRef.current.style.top  = `${outer.current.y}px`;
      }
      requestAnimationFrame(animate);
    };

    window.addEventListener('mousemove', onMove);
    const interactive = 'a, button, [role=button], input, textarea, select';
    const observe = () => {
      document.querySelectorAll(interactive).forEach(el => {
        el.addEventListener('mouseenter', onEnter);
        el.addEventListener('mouseleave', onLeave);
      });
    };
    observe();
    const observer = new MutationObserver(observe);
    observer.observe(document.body, { childList: true, subtree: true });
    const raf = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, []);

  return (
    <>
      <div ref={outerRef} className="cursor-outer" />
      <div ref={innerRef} className="cursor-inner" />
    </>
  );
}
