"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "../components/AuthContext";
import { getDocuments, uploadDocument, deleteDocument, getDocumentQuestions } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function Documents() {
  const { token } = useAuth();
  const router = useRouter();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Record<string, string[]>>({});
  const [loadingQuestions, setLoadingQuestions] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    const data = await getDocuments(token).catch(() => []);
    setDocuments(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [token]);

  const handleFile = async (file: File) => {
    if (!token) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "pdf" && ext !== "txt") {
      alert("Only .pdf and .txt files are supported.");
      return;
    }
    setUploading(true);
    setUploadStatus("UPLOADING FILE...");
    try {
      setTimeout(() => setUploadStatus("EXTRACTING TEXT..."), 1000);
      setTimeout(() => setUploadStatus("EMBEDDING CHUNKS..."), 3000);
      setTimeout(() => setUploadStatus("GENERATING SUMMARY..."), 5000);
      await uploadDocument(token, file);
      setUploadStatus("COMPLETE");
      await load();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      setUploadStatus("");
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [token]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("CONFIRM: DELETE THIS DOCUMENT?")) return;
    await deleteDocument(token!, id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (expandedId === id) setExpandedId(null);
  };

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!questions[id]) {
      setLoadingQuestions(id);
      try {
        const res = await getDocumentQuestions(token!, id);
        setQuestions((prev) => ({ ...prev, [id]: res.questions || [] }));
      } catch {
        setQuestions((prev) => ({ ...prev, [id]: [] }));
      } finally {
        setLoadingQuestions(null);
      }
    }
  };

  const askQuestion = (question: string) => {
    const encoded = encodeURIComponent(question);
    router.push(`/chat?prefill=${encoded}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="hud-kicker mb-1">// DOCUMENT INTELLIGENCE CORE</p>
          <h2 className="hud-title">DOCUMENTS</h2>
        </div>
        <div className="hud-counter w-fit">
          {documents.length} FILES
        </div>
      </div>

      {/* Upload Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-200 ${
          dragOver
            ? "border-white/50 bg-white/5"
            : "border-white/15 bg-white/[0.02] hover:border-white/30 hover:bg-white/[0.03]"
        } ${uploading ? "pointer-events-none opacity-60" : ""}`}
        style={{ clipPath: 'polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 12px 100%, 0 calc(100% - 12px))' }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-5 h-5 border border-[rgba(255,255,255,0.3)] border-t-transparent rounded-full animate-spin" />
            <p className="font-mono text-[10px] text-white/60 tracking-widest animate-pulse">{uploadStatus}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-6 h-6 text-white/30">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="font-mono text-[10px] text-white/50 tracking-widest">DROP FILE OR CLICK TO UPLOAD</p>
            <p className="font-mono text-[8px] text-white/30 tracking-widest">.PDF / .TXT SUPPORTED</p>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">LOADING DOCUMENT INDEX...</span>
        </div>
      )}

      {/* Empty State */}
      {!loading && documents.length === 0 && (
        <div className="hud-empty">[ NO DOCUMENTS UPLOADED ]</div>
      )}

      {/* Document List */}
      {!loading && documents.length > 0 && (
        <div className="space-y-3">
          <p className="font-mono text-[9px] text-white/60 tracking-widest flex items-center gap-2 mb-2">
            <span className="w-1.5 h-1.5 bg-white/60 rounded-full" />
            INDEXED FILES
          </p>
          {documents.map((doc) => {
            const isExpanded = expandedId === doc.id;
            return (
              <div
                key={doc.id}
                className="flex flex-col border border-white/10 bg-white/[0.02] hover:border-white/25 transition-colors"
                style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)' }}
              >
                <div
                  className="group flex cursor-pointer flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:gap-4"
                  onClick={() => toggleExpand(doc.id)}
                >
                  {/* File icon */}
                  <div className="shrink-0 w-8 h-8 border border-white/20 flex items-center justify-center bg-white/[0.03]">
                    <span className="font-mono text-[8px] text-white/50">
                      {doc.filename.split(".").pop()?.toUpperCase()}
                    </span>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-[11px] text-white/80 group-hover:text-white truncate">{doc.filename}</p>
                    {doc.summary && (
                      <p className="font-mono text-[9px] text-white/40 mt-0.5 line-clamp-1">{doc.summary}</p>
                    )}
                  </div>

                  {/* Chunk count */}
                  <div className="flex flex-wrap items-center gap-2 md:contents">
                    {/* Chunk count */}
                    <span className="font-mono text-[8px] text-white/40 border border-white/20 px-1.5 py-0.5 shrink-0">
                      {doc.chunk_count} CHUNKS
                    </span>

                    {/* Date */}
                    <span className="font-mono text-[8px] text-white/30 shrink-0">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>

                    {/* Delete */}
                    <button
                      onClick={(e) => handleDelete(e, doc.id)}
                      className="shrink-0 font-mono text-[8px] border border-red-500/20 text-red-500/40 px-2 py-0.5 tracking-widest hover:border-red-400/50 hover:text-red-400 transition-colors"
                    >
                      PURGE
                    </button>
                  </div>
                </div>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="px-4 py-4 border-t border-white/10 bg-black/20 space-y-4">
                    {/* Summary */}
                    {doc.summary && (
                      <div>
                        <p className="font-mono text-[8px] text-white/50 tracking-widest mb-2">SUMMARY</p>
                        <p className="font-mono text-[10px] text-white/70 leading-relaxed">{doc.summary}</p>
                      </div>
                    )}

                    {/* Questions */}
                    <div>
                      <p className="font-mono text-[8px] text-white/50 tracking-widest mb-2">SENORITA'S QUESTIONS</p>
                      {loadingQuestions === doc.id ? (
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
                          <span className="font-mono text-[9px] text-white/40">ANALYZING DOCUMENT...</span>
                        </div>
                      ) : (questions[doc.id] || []).length > 0 ? (
                        <div className="space-y-2">
                          {(questions[doc.id] || []).map((q, i) => (
                            <button
                              key={i}
                              onClick={() => askQuestion(q)}
                              className="w-full text-left px-3 py-2 border border-white/10 bg-white/[0.02] hover:border-white/30 hover:bg-white/[0.04] transition-all group"
                            >
                              <span className="font-mono text-[9px] text-white/60 group-hover:text-white/90">
                                ASK: {q}
                              </span>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="font-mono text-[9px] text-white/30">No questions generated.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
