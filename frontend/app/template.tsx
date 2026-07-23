"use client";

import { SectionReveal } from "./components/SectionReveal";

export default function Template({ children }: { children: React.ReactNode }) {
  return <SectionReveal delay={50}>{children}</SectionReveal>;
}
