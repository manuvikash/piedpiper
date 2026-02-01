const API_BASE = "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Health
export function healthCheck() {
  return request<{ status: string }>("/health");
}

// Sessions
export interface SessionResponse {
  session_id: string;
  status: string;
  phase: string | null;
  workers: WorkerSummary[] | null;
}

export interface WorkerSummary {
  worker_id: string;
  completed: boolean;
  stuck: boolean;
  actions_count: number;
  errors_count: number;
}

export interface CostResponse {
  session_id: string;
  total_spent_usd: number;
  breakdown: Record<string, number>;
  entries: CostEntry[] | null;
}

export interface CostEntry {
  timestamp: string;
  agent_type: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

export function createSession(body: {
  task: string;
  task_markdown?: string;
  budget_usd?: number;
}) {
  return request<SessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSession(sessionId: string) {
  return request<SessionResponse>(`/sessions/${sessionId}`);
}

export function getSessionCosts(sessionId: string) {
  return request<CostResponse>(`/sessions/${sessionId}/costs`);
}

// SSE Streaming
export interface StreamEvent {
  type: string;
  worker_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export function streamSession(
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  onError?: (error: Event) => void
): () => void {
  const es = new EventSource(`${API_BASE}/sessions/${sessionId}/stream`);

  es.onmessage = (msg) => {
    try {
      const event: StreamEvent = JSON.parse(msg.data);
      onEvent(event);
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = (err) => {
    onError?.(err);
    es.close();
  };

  return () => es.close();
}

// Review
export interface ReviewItem {
  id: string;
  timestamp: string;
  question: string;
  worker_id: string;
  worker_context: string;
  arbiter_urgency: number;
  arbiter_classification: string;
  similar_cached: Record<string, unknown>[];
  status: string;
  reviewer_id: string | null;
  reviewed_at: string | null;
}

export interface ReviewDecisionBody {
  review_id: string;
  decision: "pending" | "approved" | "rejected" | "modified";
  reviewer_id: string;
  reason?: string;
  corrected_answer?: string;
  correction_reason?: string;
}

export function listReviewItems() {
  return request<ReviewItem[]>("/review/items");
}

export function listPendingReviewItems() {
  return request<ReviewItem[]>("/review/items/pending");
}

export function getReviewItem(reviewId: string) {
  return request<ReviewItem>(`/review/items/${reviewId}`);
}

export function submitReviewDecision(
  reviewId: string,
  decision: ReviewDecisionBody
) {
  return request<{ status: string }>(`/review/items/${reviewId}/decide`, {
    method: "POST",
    body: JSON.stringify(decision),
  });
}
