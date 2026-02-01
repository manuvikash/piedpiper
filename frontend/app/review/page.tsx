"use client";

import { useState, useEffect } from "react";
import {
  listReviewItems,
  listPendingReviewItems,
  getReviewItem,
  submitReviewDecision,
  type ReviewItem,
  type ReviewDecisionBody,
} from "@/lib/api";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "pending">("all");

  // Single item lookup
  const [lookupId, setLookupId] = useState("");
  const [singleItem, setSingleItem] = useState<ReviewItem | null>(null);
  const [lookupError, setLookupError] = useState("");

  // Decision form
  const [selectedItem, setSelectedItem] = useState<ReviewItem | null>(null);
  const [decision, setDecision] = useState<
    "approved" | "rejected" | "modified"
  >("approved");
  const [reviewerId, setReviewerId] = useState("reviewer-1");
  const [reason, setReason] = useState("");
  const [correctedAnswer, setCorrectedAnswer] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState("");

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const data =
        filter === "pending"
          ? await listPendingReviewItems()
          : await listReviewItems();
      setItems(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch review items"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchItems();
  }, [filter]);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    setLookupError("");
    setSingleItem(null);
    try {
      const item = await getReviewItem(lookupId);
      setSingleItem(item);
    } catch (err: unknown) {
      setLookupError(err instanceof Error ? err.message : "Not found");
    }
  }

  async function handleSubmitDecision(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedItem) return;
    setSubmitting(true);
    setSubmitResult("");
    try {
      const body: ReviewDecisionBody = {
        review_id: selectedItem.id,
        decision,
        reviewer_id: reviewerId,
        reason: reason || undefined,
        corrected_answer:
          decision === "modified" ? correctedAnswer || undefined : undefined,
        correction_reason:
          decision === "modified" ? correctionReason || undefined : undefined,
      };
      await submitReviewDecision(selectedItem.id, body);
      setSubmitResult("Decision submitted successfully");
      setSelectedItem(null);
      setReason("");
      setCorrectedAnswer("");
      setCorrectionReason("");
      fetchItems();
    } catch (err: unknown) {
      setSubmitResult(
        err instanceof Error ? err.message : "Failed to submit"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Review Queue</h1>

      {/* Filter & Refresh */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setFilter("all")}
          className={`rounded px-3 py-1 text-sm ${
            filter === "all"
              ? "bg-white text-black"
              : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
          }`}
        >
          All Items
        </button>
        <button
          onClick={() => setFilter("pending")}
          className={`rounded px-3 py-1 text-sm ${
            filter === "pending"
              ? "bg-white text-black"
              : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
          }`}
        >
          Pending Only
        </button>
        <button
          onClick={fetchItems}
          className="rounded px-3 py-1 text-sm bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
        >
          Refresh
        </button>
      </div>

      {/* Items List */}
      {loading && <p className="text-sm text-zinc-500">Loading...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!loading && items.length === 0 && (
        <p className="text-sm text-zinc-500">
          No review items found. Items appear here when workers raise questions
          during a session.
        </p>
      )}

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.id}
              className="rounded border border-zinc-800 p-4 space-y-2"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="text-sm font-medium">{item.question}</div>
                  <div className="text-xs text-zinc-500">
                    Worker: {item.worker_id} | Urgency:{" "}
                    {item.arbiter_urgency.toFixed(2)} | Class:{" "}
                    {item.arbiter_classification || "\u2014"}
                  </div>
                  {item.worker_context && (
                    <div className="text-xs text-zinc-500 mt-1">
                      Context: {item.worker_context}
                    </div>
                  )}
                </div>
                <ReviewStatusBadge status={item.status} />
              </div>
              <div className="text-xs text-zinc-600">
                ID: {item.id} | {item.timestamp}
              </div>
              {item.similar_cached.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-zinc-400">
                    Similar cached ({item.similar_cached.length})
                  </summary>
                  <pre className="mt-1 rounded bg-zinc-900 p-2 overflow-x-auto">
                    {JSON.stringify(item.similar_cached, null, 2)}
                  </pre>
                </details>
              )}
              {item.status === "pending" && (
                <button
                  onClick={() => {
                    setSelectedItem(item);
                    setSubmitResult("");
                  }}
                  className="rounded bg-zinc-700 px-3 py-1 text-xs hover:bg-zinc-600"
                >
                  Review
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Single Item Lookup */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Lookup by ID</h2>
        <form onSubmit={handleLookup} className="flex gap-2">
          <input
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            className="flex-1 rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm font-mono focus:outline-none focus:border-zinc-500"
            placeholder="Review item ID"
          />
          <button
            type="submit"
            disabled={!lookupId}
            className="rounded bg-zinc-700 px-4 py-2 text-sm hover:bg-zinc-600 disabled:opacity-50"
          >
            Fetch
          </button>
        </form>
        {lookupError && (
          <p className="text-red-400 text-sm mt-2">{lookupError}</p>
        )}
        {singleItem && (
          <div className="mt-3 rounded border border-zinc-800 p-3">
            <pre className="text-xs overflow-x-auto">
              {JSON.stringify(singleItem, null, 2)}
            </pre>
          </div>
        )}
      </section>

      {/* Decision Modal */}
      {selectedItem && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6 w-full max-w-lg space-y-4">
            <h3 className="text-lg font-semibold">Submit Decision</h3>
            <p className="text-sm text-zinc-400">{selectedItem.question}</p>
            <form onSubmit={handleSubmitDecision} className="space-y-3">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">
                  Decision
                </label>
                <select
                  value={decision}
                  onChange={(e) =>
                    setDecision(
                      e.target.value as "approved" | "rejected" | "modified"
                    )
                  }
                  className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                >
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="modified">Modified</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">
                  Reviewer ID
                </label>
                <input
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">
                  Reason
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={2}
                  className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                />
              </div>
              {decision === "modified" && (
                <>
                  <div>
                    <label className="block text-sm text-zinc-400 mb-1">
                      Corrected Answer
                    </label>
                    <textarea
                      value={correctedAnswer}
                      onChange={(e) => setCorrectedAnswer(e.target.value)}
                      rows={3}
                      className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-zinc-400 mb-1">
                      Correction Reason
                    </label>
                    <textarea
                      value={correctionReason}
                      onChange={(e) => setCorrectionReason(e.target.value)}
                      rows={2}
                      className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                    />
                  </div>
                </>
              )}
              {submitResult && (
                <p
                  className={`text-sm ${
                    submitResult.includes("success")
                      ? "text-green-400"
                      : "text-red-400"
                  }`}
                >
                  {submitResult}
                </p>
              )}
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded bg-white text-black px-4 py-2 text-sm font-medium hover:bg-zinc-200 disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit Decision"}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedItem(null)}
                  className="rounded bg-zinc-800 px-4 py-2 text-sm hover:bg-zinc-700"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-yellow-900/50 text-yellow-400",
    approved: "bg-green-900/50 text-green-400",
    rejected: "bg-red-900/50 text-red-400",
    modified: "bg-blue-900/50 text-blue-400",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        styles[status] ?? "bg-zinc-800 text-zinc-400"
      }`}
    >
      {status}
    </span>
  );
}
