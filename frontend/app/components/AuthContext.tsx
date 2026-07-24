"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

interface AuthContextType {
  token: string | null;
  userId: string | null;
  setAuth: (token: string, userId: string) => void;
  setToken: (token: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Read synchronously so token/userId are non-null on the very first render —
  // avoids the race where the voice hook fires before the hydration effect.
  const [token, setTokenState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("senorita_token");
  });

  const [userId, setUserIdState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("senorita_user_id");
  });

  /** Call this after a successful login/setup where we have both values. */
  const setAuth = (newToken: string, newUserId: string) => {
    setTokenState(newToken);
    setUserIdState(newUserId);
    localStorage.setItem("senorita_token", newToken);
    localStorage.setItem("senorita_user_id", newUserId);
  };

  /** Legacy single-token setter — keeps userId intact. */
  const setToken = (newToken: string | null) => {
    setTokenState(newToken);
    if (newToken) {
      localStorage.setItem("senorita_token", newToken);
    } else {
      localStorage.removeItem("senorita_token");
      localStorage.removeItem("senorita_user_id");
      setUserIdState(null);
    }
  };

  const logout = () => setToken(null);

  return (
    <AuthContext.Provider value={{ token, userId, setAuth, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
