'use client';

import { NetraLogo } from '@/components/logo/NetraLogo';
import { Globe, ExternalLink, Link2 } from 'lucide-react';

const NAV_GROUPS = [
  {
    title: 'Product',
    links: ['Features', 'Pricing', 'Changelog', 'Roadmap'],
  },
  {
    title: 'Developers',
    links: ['Documentation', 'API Reference', 'GitHub', 'Status'],
  },
  {
    title: 'Company',
    links: ['About', 'Blog', 'Careers', 'Contact'],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-border py-16" style={{ background: 'var(--color-void)' }}>
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10">
          {/* Brand */}
          <div className="col-span-2">
            <NetraLogo size={28} variant="full" animated={false} className="mb-4" />
            <p className="text-text-ghost text-sm max-w-xs leading-relaxed mb-6">
              Static analysis, vulnerability detection, and automated secure code patching.
            </p>
            <div className="flex items-center gap-4">
              <a href="#" className="text-text-ghost hover:text-teal transition-colors" aria-label="GitHub">
                <Globe size={18} />
              </a>
              <a href="#" className="text-text-ghost hover:text-teal transition-colors" aria-label="Twitter">
                <ExternalLink size={18} />
              </a>
              <a href="#" className="text-text-ghost hover:text-teal transition-colors" aria-label="LinkedIn">
                <Link2 size={18} />
              </a>
            </div>
          </div>

          {/* Nav groups */}
          {NAV_GROUPS.map(group => (
            <div key={group.title}>
              <h4 className="font-display text-sm font-medium text-text-muted mb-4">{group.title}</h4>
              <ul className="space-y-2.5">
                {group.links.map(link => (
                  <li key={link}>
                    <a
                      href="#"
                      className="text-text-ghost text-sm hover:text-text-primary transition-colors duration-200"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 mt-16 pt-8 border-t border-border">
          <span className="text-text-ghost text-xs">© {new Date().getFullYear()} Netra. All rights reserved.</span>
          <div className="flex gap-6 text-text-ghost text-xs">
            <a href="#" className="hover:text-text-primary transition-colors">Privacy</a>
            <a href="#" className="hover:text-text-primary transition-colors">Terms</a>
            <a href="#" className="hover:text-text-primary transition-colors">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
