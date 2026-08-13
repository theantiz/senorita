const API_BASE = typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "http://localhost:8000";

/** Clear auth state and redirect to login (called on any 401). */
function handleUnauthorized() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("senorita_token");
  localStorage.removeItem("senorita_user_id");
  window.location.reload();
}

export async function apiFetch(endpoint: string, options: RequestInit = {}, token: string | null = null) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    if (response.status === 401) {
      handleUnauthorized();
      throw new Error(`Unauthorized (401)`);
    }
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  
  return response.json();
}

export async function setupAuth(name: string, timezone: string) {
  return apiFetch("/auth/setup", {
    method: "POST",
    body: JSON.stringify({ name, timezone })
  });
}

export async function loginUser(name: string) {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export async function getContacts(token: string) {
  return apiFetch("/contacts", {}, token);
}

export async function getTasks(token: string) {
  return apiFetch("/tasks", {}, token);
}

export async function getCalendarEvents(token: string) {
  return apiFetch("/calendar", {}, token);
}

export async function getReminders(token: string) {
  return apiFetch("/reminders", {}, token);
}

export async function getMemory(token: string) {
  return apiFetch("/memory", {}, token);
}

export async function getActivity(token: string) {
  return apiFetch("/activity", {}, token);
}

export async function sendChatMessage(token: string, message: string) {
  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message })
  }, token);
}

export async function sendVoiceMessage(token: string, formData: FormData) {
  const headers: Record<string, string> = {
    "Authorization": `Bearer ${token}`
  };
  
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 60000);
  
  try {
    const response = await fetch(`${API_BASE}/chat/voice`, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal
    });
    
    clearTimeout(id);
    
    if (!response.ok) {
      if (response.status === 401) {
        handleUnauthorized();
        throw new Error("Unauthorized (401)");
      }
      throw new Error(`API Error: ${response.statusText}`);
    }
    
    return response.json();
  } catch (err: any) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error("API Error: Request timed out after 60 seconds");
    }
    throw err;
  }
}

export async function deleteMemory(token: string, id: string) {
  return apiFetch(`/memory/${id}`, { method: "DELETE" }, token);
}

export interface MemoryFilters {
  category?: string;
  search?: string;
  source_ref?: string;
  locked?: boolean;
  date_from?: string;
  date_to?: string;
}

export async function getMemories(token: string, filters?: MemoryFilters) {
  let query = "";
  if (filters) {
    const params = new URLSearchParams();
    if (filters.category) params.append("category", filters.category);
    if (filters.search) params.append("search", filters.search);
    if (filters.source_ref) params.append("source_ref", filters.source_ref);
    if (filters.locked !== undefined) params.append("locked", String(filters.locked));
    if (filters.date_from) params.append("date_from", filters.date_from);
    if (filters.date_to) params.append("date_to", filters.date_to);
    const q = params.toString();
    if (q) query = `?${q}`;
  }
  return apiFetch(`/api/v1/memory${query}`, {}, token);
}

export async function patchMemoryLock(token: string, id: string) {
  return apiFetch(`/memory/${id}/lock`, { method: "PATCH" }, token);
}

/** Generate speech via backend edge-tts and return base64 MP3, or null on failure. */
export async function speakText(token: string, text: string): Promise<string | null> {
  try {
    const res = await apiFetch("/chat/tts", {
      method: "POST",
      body: JSON.stringify({ text }),
    }, token);
    return res.audio_base64 ?? null;
  } catch {
    return null;
  }
}

export async function getLatestBriefing(token: string) {
  return apiFetch("/api/v1/briefings/latest?type=daily", {}, token);
}

export async function getLatestEodBriefing(token: string) {
  return apiFetch("/api/v1/briefings/latest?type=end_of_day", {}, token);
}

export async function getRecentNotifications(token: string) {
  return apiFetch("/api/v1/notifications/recent", {}, token);
}
