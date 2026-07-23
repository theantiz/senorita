const API_BASE = "http://localhost:8000";

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
    throw new Error(`API Error: ${response.statusText}`);
  }
  
  return response.json();
}

export async function setupAuth(name: string, timezone: string) {
  return apiFetch("/auth/setup", {
    method: "POST",
    body: JSON.stringify({ name, timezone })
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
  
  const response = await fetch(`http://localhost:8000/chat/voice`, {
    method: "POST",
    headers,
    body: formData
  });
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }
  
  return response.json();
}

export async function deleteMemory(token: string, id: string) {
  return apiFetch(`/memory/${id}`, { method: "DELETE" }, token);
}

export async function patchMemoryLock(token: string, id: string) {
  return apiFetch(`/memory/${id}/lock`, { method: "PATCH" }, token);
}
