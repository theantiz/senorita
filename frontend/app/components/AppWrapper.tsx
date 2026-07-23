"use client";

import React, { useState } from "react";
import { useAuth } from "./AuthContext";
import { loginUser, setupAuth } from "@/lib/api";
import { SectionReveal } from "./SectionReveal";

export function AppWrapper({ children }: { children: React.ReactNode }) {
  const { token, setToken } = useAuth();
  const [activeTab, setActiveTab] = useState<"login" | "token" | "setup">("login");
  const [tokenInput, setTokenInput] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [setupNameInput, setSetupNameInput] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nameInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await loginUser(nameInput.trim());
      if (res.token) {
        setToken(res.token);
      }
    } catch (err: any) {
      setError("Login failed. Try using 'admin' or check the server logs for the admin token.");
    } finally {
      setLoading(false);
    }
  };

  const handleTokenLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      // Validate the token by making a quick API call
      const { getActivity } = await import("@/lib/api");
      await getActivity(tokenInput.trim());
      setToken(tokenInput.trim());
    } catch (err: any) {
      setError("Invalid or expired token. Try logging in with your name instead.");
    } finally {
      setLoading(false);
    }
  };

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setupNameInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const res = await setupAuth(setupNameInput.trim(), timezone);
      if (res.token) {
        setToken(res.token);
      }
    } catch (err: any) {
      setError(err.message || "Failed to setup profile");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-[#070b14] text-white">
        {/* Subtle grid */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:24px_24px]" />

        {/* Decorative corner markers */}
        <div className="absolute top-8 left-8 w-8 h-8 border-t border-l border-[rgba(255,255,255,0.2)]" />
        <div className="absolute top-8 right-8 w-8 h-8 border-t border-r border-[rgba(255,255,255,0.2)]" />
        <div className="absolute bottom-8 left-8 w-8 h-8 border-b border-l border-[rgba(255,255,255,0.2)]" />
        <div className="absolute bottom-8 right-8 w-8 h-8 border-b border-r border-[rgba(255,255,255,0.2)]" />

        <SectionReveal delay={100}>
          <div className="relative z-10 w-full max-w-md mx-6">
            <div className="text-center mb-10">
              <h1 className="font-display text-4xl font-semibold tracking-wide text-white">SEÑORITA</h1>
              <p className="font-mono text-xs text-white/40 tracking-widest mt-3 uppercase">OS // Secure Boot</p>
            </div>

            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.09)] backdrop-blur-md p-8">
              {/* Tabs */}
              <div className="flex mb-8 border-b border-[rgba(255,255,255,0.09)]">
                <button
                  onClick={() => { setActiveTab("login"); setError(""); }}
                  className={`flex-1 pb-3 text-xs font-mono tracking-widest uppercase transition-colors ${
                    activeTab === "login" ? "text-white border-b border-white" : "text-white/40 hover:text-white/70"
                  }`}
                >
                  Login
                </button>
                <button
                  onClick={() => { setActiveTab("token"); setError(""); }}
                  className={`flex-1 pb-3 text-xs font-mono tracking-widest uppercase transition-colors ${
                    activeTab === "token" ? "text-white border-b border-white" : "text-white/40 hover:text-white/70"
                  }`}
                >
                  Token
                </button>
                <button
                  onClick={() => { setActiveTab("setup"); setError(""); }}
                  className={`flex-1 pb-3 text-xs font-mono tracking-widest uppercase transition-colors ${
                    activeTab === "setup" ? "text-white border-b border-white" : "text-white/40 hover:text-white/70"
                  }`}
                >
                  New Profile
                </button>
              </div>

              {error && (
                <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 text-red-400 font-mono text-xs">
                  {error}
                </div>
              )}

              {activeTab === "login" ? (
                <form onSubmit={handleLogin} className="space-y-6">
                  <div>
                    <label className="block font-mono text-[10px] text-white/50 tracking-widest mb-2 uppercase">User Name</label>
                    <input
                      type="text"
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      className="w-full bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.09)] px-4 py-3 text-sm text-white font-mono placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors"
                      placeholder="Enter your name..."
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-white text-black font-display font-medium text-sm px-4 py-3 hover:bg-white/90 transition-colors tracking-wide disabled:opacity-50"
                  >
                    {loading ? "AUTHENTICATING..." : "LOGIN TO SYSTEM"}
                  </button>
                  <p className="font-mono text-[9px] text-white/30 text-center tracking-wider">
                    First-time login creates a new profile. Check server console for admin token.
                  </p>
                </form>
              ) : activeTab === "token" ? (
                <form onSubmit={handleTokenLogin} className="space-y-6">
                  <div>
                    <label className="block font-mono text-[10px] text-white/50 tracking-widest mb-2 uppercase">Access Token</label>
                    <input
                      type="password"
                      value={tokenInput}
                      onChange={(e) => setTokenInput(e.target.value)}
                      className="w-full bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.09)] px-4 py-3 text-sm text-white font-mono placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors"
                      placeholder="Paste token here..."
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-white text-black font-display font-medium text-sm px-4 py-3 hover:bg-white/90 transition-colors tracking-wide disabled:opacity-50"
                  >
                    {loading ? "VALIDATING..." : "AUTHENTICATE"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleSetup} className="space-y-6">
                  <div>
                    <label className="block font-mono text-[10px] text-white/50 tracking-widest mb-2 uppercase">User Identifier</label>
                    <input
                      type="text"
                      value={setupNameInput}
                      onChange={(e) => setSetupNameInput(e.target.value)}
                      className="w-full bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.09)] px-4 py-3 text-sm text-white font-mono placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors"
                      placeholder="Your Name..."
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-white text-black font-display font-medium text-sm px-4 py-3 hover:bg-white/90 transition-colors tracking-wide disabled:opacity-50"
                  >
                    {loading ? "INITIALIZING..." : "CREATE PROFILE"}
                  </button>
                </form>
              )}
            </div>
          </div>
        </SectionReveal>
      </div>
    );
  }

  return <>{children}</>;
}
