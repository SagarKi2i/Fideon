import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";

export interface DecisionReviewPayload {
  pod_model_id: string;
  pod_model_name: string;
  domain: string;
  decision_type: string;
  title: string;
  summary?: string | null;
  ai_recommendation?: string | null;
  confidence_score?: number | null;
  threshold_exceeded?: boolean;
  input_data?: Record<string, any>;
  output_data?: Record<string, any>;
}

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw notAuthenticatedError();
  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

export async function createDecisionReview(payload: DecisionReviewPayload) {
  const response = await fetch(apiUrl("/api/reviews"), {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(payload),
  });
  const data = await readJsonSafe(response);
  if (!response.ok) {
    throw buildApiRequestError(response, data, "Failed to send review request");
  }
  return data;
}

export async function listMyDecisionReviews() {
  const response = await fetch(apiUrl("/api/reviews/my"), {
    headers: await authHeaders(),
  });
  const data = await readJsonSafe(response);
  if (!response.ok) {
    throw buildApiRequestError(response, data, "Failed to load your review requests");
  }
  return data.reviews ?? [];
}

export async function listAllDecisionReviews() {
  const response = await fetch(apiUrl("/api/reviews"), {
    headers: await authHeaders(),
  });
  const data = await readJsonSafe(response);
  if (!response.ok) {
    throw buildApiRequestError(response, data, "Failed to load review queue");
  }
  return data.reviews ?? [];
}

export async function approveDecisionReview(reviewId: string, reviewerNotes?: string) {
  const response = await fetch(apiUrl(`/api/reviews/${reviewId}/approve`), {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ reviewer_notes: reviewerNotes ?? "" }),
  });
  const data = await readJsonSafe(response);
  if (!response.ok) {
    throw buildApiRequestError(response, data, "Failed to approve review");
  }
  return data;
}

export async function rejectDecisionReview(reviewId: string, reviewerNotes?: string) {
  const response = await fetch(apiUrl(`/api/reviews/${reviewId}/reject`), {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ reviewer_notes: reviewerNotes ?? "" }),
  });
  const data = await readJsonSafe(response);
  if (!response.ok) {
    throw buildApiRequestError(response, data, "Failed to reject review");
  }
  return data;
}
