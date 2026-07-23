"use client";

import React, { useEffect, useState } from "react";

export function SectionReveal({ children, delay = 0 }: { children: React.ReactNode, delay?: number }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  return (
    <div
      className={`transition-all duration-700 ease-out will-change-transform ${
        show
          ? "opacity-100 translate-y-0 scale-100 blur-none"
          : "opacity-0 translate-y-4 scale-[0.98] blur-[4px]"
      }`}
    >
      {children}
    </div>
  );
}
