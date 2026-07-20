'use client';

import { useEffect, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

export default function RouteLoader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);

  // Stop loading when route changes
  useEffect(() => {
    setLoading(false);
  }, [pathname, searchParams]);

  useEffect(() => {
    const handleAnchorClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const anchor = target.closest('a');
      if (anchor) {
        const href = anchor.getAttribute('href');
        const targetAttr = anchor.getAttribute('target');
        if (
          href &&
          !href.startsWith('http') &&
          !href.startsWith('mailto:') &&
          !href.startsWith('tel:') &&
          !href.startsWith('#') &&
          targetAttr !== '_blank'
        ) {
          try {
            const currentUrl = new URL(window.location.href);
            const targetUrl = new URL(href, window.location.href);
            if (
              currentUrl.pathname !== targetUrl.pathname ||
              currentUrl.search !== targetUrl.search
            ) {
              setLoading(true);
            }
          } catch {
            // ignore
          }
        }
      }
    };

    const originalPushState = window.history.pushState;
    const originalReplaceState = window.history.replaceState;

    window.history.pushState = function (...args) {
      setLoading(true);
      return originalPushState.apply(this, args);
    };
    window.history.replaceState = function (...args) {
      setLoading(true);
      return originalReplaceState.apply(this, args);
    };

    document.addEventListener('click', handleAnchorClick);
    return () => {
      document.removeEventListener('click', handleAnchorClick);
      window.history.pushState = originalPushState;
      window.history.replaceState = originalReplaceState;
    };
  }, []);

  if (!loading) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-bg-primary/60 backdrop-blur-sm pointer-events-none">
      <div className="flex items-center gap-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-3 h-3 rounded-full bg-text-primary"
            style={{
              animation: `dotBounce 1.2s ease-in-out infinite`,
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>
      <style>{`
        @keyframes dotBounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
