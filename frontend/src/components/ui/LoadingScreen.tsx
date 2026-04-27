'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { NetraLogo } from '@/components/logo/NetraLogo';

export function LoadingScreen() {
  const [loaded, setLoaded] = useState(false);
  const [show, setShow]     = useState(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (sessionStorage.getItem('netra-loaded')) {
      setShow(false);
      return;
    }
    const timer = setTimeout(() => {
      setLoaded(true);
      sessionStorage.setItem('netra-loaded', '1');
      setTimeout(() => setShow(false), 700);
    }, 1800);
    return () => clearTimeout(timer);
  }, []);

  if (!show) return null;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 1.06 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-0 z-[10000] flex flex-col items-center justify-center"
          style={{ background: '#040810' }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <NetraLogo variant="icon" size={64} animated />
          </motion.div>

          <div className="mt-8 w-[min(600px,80vw)] h-px bg-border relative overflow-hidden">
            <motion.div
              className="absolute inset-y-0 left-0"
              style={{ background: 'var(--color-teal)' }}
              initial={{ width: '0%' }}
              animate={{ width: loaded ? '100%' : '70%' }}
              transition={{ duration: loaded ? 0.3 : 1.5, ease: [0.16, 1, 0.3, 1] }}
            />
            {loaded && (
              <motion.div
                className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full"
                style={{ background: 'var(--color-amber)' }}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: 'spring' }}
              />
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
