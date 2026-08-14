"use client";

import { SectionReveal } from "./components/SectionReveal";
import { useRef, useState, useEffect } from "react";
import { usePathname } from "next/navigation";

/**
 * Template wraps each page. In Next.js, template.tsx re-mounts on every
 * route change — which is intentional for entrance animations.
 *
 * We only play the reveal animation on the FIRST visit to each unique route.
 * Subsequent navigations back to an already-seen route skip the animation,
 * keeping the experience snappy when switching sidebar tabs.
 */

const visitedRoutes = new Set<string>();

export default function Template({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFirstVisit = !visitedRoutes.has(pathname);

  useEffect(() => {
    visitedRoutes.add(pathname);
  }, [pathname]);

  if (isFirstVisit) {
    return <SectionReveal delay={50}>{children}</SectionReveal>;
  }

  // Already visited — render immediately, no animation
  return <>{children}</>;
}
