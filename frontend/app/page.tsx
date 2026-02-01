"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  healthCheck,
  createSession,
  streamSession,
  getSession,
  getSessionCosts,
  type SessionResponse,
  type CostResponse,
  type StreamEvent,
} from "@/lib/api";

const WORKER_IDS = ["worker-1", "worker-2", "worker-3"];

interface LogEntry {
  id: number;
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface PreviewUrl {
  port: number;
  url: string;
}

interface WorkerState {
  status: "idle" | "thinking" | "running" | "done" | "error" | "stuck";
  logs: LogEntry[];
  confidence: number;
  previewUrls: PreviewUrl[];
}

function initialWorkerState(): WorkerState {
  return { status: "idle", logs: [], confidence: 0, previewUrls: [] };
}

export default function Home() {
  const [health, setHealth] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string>("idle");
  const [sessionStatus, setSessionStatus] = useState<string>("idle");
  const [costs, setCosts] = useState<CostResponse | null>(null);

  const [workers, setWorkers] = useState<Record<string, WorkerState>>({
    "worker-1": initialWorkerState(),
    "worker-2": initialWorkerState(),
    "worker-3": initialWorkerState(),
  });

  const logIdRef = useRef(0);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    healthCheck()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("unreachable"));
  }, []);

  const handleEvent = useCallback((event: StreamEvent) => {
    const wid = event.worker_id;
    const entry: LogEntry = {
      id: ++logIdRef.current,
      type: event.type,
      data: event.data,
      timestamp: event.timestamp,
    };

    // System-level events
    if (wid === "system") {
      if (event.type === "phase_change") {
        setPhase(event.data.phase as string);
      }
      if (event.type === "session_done") {
        setSessionStatus(event.data.status as string);
        // Fetch final costs
        setSessionId((sid) => {
          if (sid) {
            getSessionCosts(sid).then(setCosts).catch(() => {});
          }
          return sid;
        });
      }
      return;
    }

    // Worker-level events
    setWorkers((prev) => {
      const worker = prev[wid];
      if (!worker) return prev;

      const updated = { ...worker, logs: [...worker.logs, entry] };

      switch (event.type) {
        case "ready":
        case "task_assigned":
          updated.status = "idle";
          break;
        case "thinking":
          updated.status = "thinking";
          break;
        case "thought":
          updated.status = "thinking";
          updated.confidence = (event.data.confidence as number) ?? 0;
          break;
        case "code_running":
          updated.status = "running";
          break;
        case "code_result":
          updated.status = (event.data.success as boolean)
            ? "done"
            : "error";
          break;
        case "completed":
          updated.status = "done";
          break;
        case "preview_url":
          updated.previewUrls = (event.data.urls as PreviewUrl[]) ?? [];
          break;
        case "error":
          updated.status = "error";
          break;
        case "stuck":
          updated.status = "stuck";
          break;
      }

      return { ...prev, [wid]: updated };
    });
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!task.trim()) return;

    // Reset state
    setCreating(true);
    setCreateError("");
    setCosts(null);
    setPhase("init");
    setSessionStatus("running");
    setWorkers({
      "worker-1": initialWorkerState(),
      "worker-2": initialWorkerState(),
      "worker-3": initialWorkerState(),
    });
    logIdRef.current = 0;

    // Cleanup previous stream
    cleanupRef.current?.();

    try {
      const res = await createSession({ task });
      setSessionId(res.session_id);

      // Connect SSE
      const cleanup = streamSession(
        res.session_id,
        handleEvent,
        () => {
          // On SSE error, fall back to polling final state
          getSession(res.session_id).then((s) => {
            setSessionStatus(s.status);
            setPhase(s.phase ?? "unknown");
          }).catch(() => {});
          getSessionCosts(res.session_id).then(setCosts).catch(() => {});
        }
      );
      cleanupRef.current = cleanup;
    } catch (err: unknown) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create session"
      );
      setSessionStatus("idle");
    } finally {
      setCreating(false);
      setTask("");
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanupRef.current?.();
  }, []);

  const isActive = sessionStatus === "running";

  return (
    <div className="flex flex-col gap-6 h-[calc(100vh-57px)]">
      {/* Top bar: create session */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              health === "ok"
                ? "bg-green-500"
                : health === "unreachable"
                  ? "bg-red-500"
                  : "bg-yellow-500 animate-pulse"
            }`}
          />
          <span className="text-xs text-zinc-500">
            {health === "ok" ? "API" : health ?? "..."}
          </span>
        </div>

        <form onSubmit={handleCreate} className="flex flex-1 gap-2">
          <input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe a task for the workers..."
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600"
            disabled={creating}
          />
          <button
            type="submit"
            disabled={creating || !task.trim()}
            className="rounded-lg bg-white text-black px-5 py-2.5 text-sm font-medium hover:bg-zinc-200 disabled:opacity-40 transition-colors"
          >
            {creating ? "Starting..." : "Run"}
          </button>
        </form>

        {sessionId && (
          <span className="text-xs text-zinc-600 font-mono">
            {sessionId.slice(0, 8)}
          </span>
        )}
      </div>

      {createError && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-2 text-sm text-red-400">
          {createError}
        </div>
      )}

      {/* Phase + Status bar */}
      {sessionId && (
        <div className="flex items-center gap-4 text-xs">
          <PhaseIndicator phase={phase} />
          <StatusBadge status={sessionStatus} />
          {costs && (
            <span className="text-zinc-500 ml-auto">
              Cost: ${costs.total_spent_usd.toFixed(4)}
            </span>
          )}
        </div>
      )}

      {/* 3 Worker Columns */}
      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        {WORKER_IDS.map((wid) => (
          <WorkerColumn
            key={wid}
            workerId={wid}
            state={workers[wid]}
            isActive={isActive}
          />
        ))}
      </div>

      {/* Cost breakdown at bottom */}
      {costs && costs.total_spent_usd > 0 && (
        <div className="flex gap-3 text-xs text-zinc-500 pb-2">
          {Object.entries(costs.breakdown)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => (
              <span key={k}>
                {k}: ${v.toFixed(4)}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

function WorkerColumn({
  workerId,
  state,
  isActive,
}: {
  workerId: string;
  state: WorkerState;
  isActive: boolean;
}) {
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.logs.length]);

  return (
    <div className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <WorkerStatusDot status={state.status} />
          <span className="text-sm font-medium">{workerId}</span>
        </div>
        {state.confidence > 0 && (
          <span className="text-xs text-zinc-500">
            {(state.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Preview iframe */}
      {state.previewUrls.length > 0 && (
        <div className="border-b border-zinc-800">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Preview</span>
            {state.previewUrls.map((p) => (
              <a
                key={p.port}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-blue-400 hover:text-blue-300 underline"
              >
                :{p.port}
              </a>
            ))}
          </div>
          <iframe
            src={state.previewUrls[0].url}
            className="w-full h-48 bg-white"
            sandbox="allow-scripts allow-same-origin allow-forms"
            title={`${workerId} preview`}
          />
        </div>
      )}

      {/* Activity feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {state.logs.length === 0 && (
          <p className="text-xs text-zinc-600 text-center py-8">
            {isActive ? "Waiting..." : "No activity yet"}
          </p>
        )}
        {state.logs.map((log) => (
          <LogItem key={log.id} log={log} />
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

function LogItem({ log }: { log: LogEntry }) {
  switch (log.type) {
    case "ready":
      return (
        <div className="text-xs text-zinc-600">
          Sandbox ready
        </div>
      );
    case "task_assigned":
      return (
        <div className="text-xs text-blue-400">
          Task assigned
        </div>
      );
    case "thinking":
      return (
        <div className="text-xs text-yellow-500 animate-pulse">
          Thinking...
        </div>
      );
    case "thought":
      return (
        <div className="rounded-lg bg-zinc-900 p-3 text-xs space-y-1">
          <div className="text-zinc-300">
            {log.data.thought as string}
          </div>
          {log.data.has_code ? (
            <div className="text-zinc-500 text-[10px]">
              has code to execute
            </div>
          ) : null}
        </div>
      );
    case "code_running":
      return (
        <div className="rounded-lg border border-zinc-800 p-3 text-xs space-y-1">
          <div className="text-yellow-500 font-mono text-[10px]">
            Running {log.data.lines as number} lines...
          </div>
          <pre className="text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap text-[11px]">
            {log.data.code as string}
          </pre>
        </div>
      );
    case "code_result": {
      const success = log.data.success as boolean;
      return (
        <div
          className={`rounded-lg p-3 text-xs font-mono ${
            success
              ? "bg-green-950/30 border border-green-900/40 text-green-300"
              : "bg-red-950/30 border border-red-900/40 text-red-300"
          }`}
        >
          <div className="text-[10px] mb-1 opacity-70">
            {success ? "SUCCESS" : "FAILED"}
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px]">
            {log.data.output as string}
          </pre>
        </div>
      );
    }
    case "completed":
      return (
        <div className="rounded-lg bg-green-950/30 border border-green-900/40 p-3 text-xs text-green-400">
          Task completed
        </div>
      );
    case "error":
      return (
        <div className="rounded-lg bg-red-950/30 border border-red-900/40 p-3 text-xs text-red-400">
          {log.data.error as string}
        </div>
      );
    case "preview_url": {
      const urls = log.data.urls as PreviewUrl[];
      return (
        <div className="rounded-lg bg-blue-950/30 border border-blue-900/40 p-3 text-xs text-blue-300 space-y-1">
          <div className="font-medium">Preview available</div>
          <div className="flex flex-wrap gap-2">
            {urls?.map((p) => (
              <a
                key={p.port}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline"
              >
                Port {p.port}
              </a>
            ))}
          </div>
        </div>
      );
    }
    case "stuck":
      return (
        <div className="text-xs text-orange-400">
          Stuck: {log.data.reason as string}
        </div>
      );
    default:
      return (
        <div className="text-xs text-zinc-600">
          {log.type}: {JSON.stringify(log.data)}
        </div>
      );
  }
}

function WorkerStatusDot({ status }: { status: WorkerState["status"] }) {
  const styles: Record<string, string> = {
    idle: "bg-zinc-600",
    thinking: "bg-yellow-500 animate-pulse",
    running: "bg-blue-500 animate-pulse",
    done: "bg-green-500",
    error: "bg-red-500",
    stuck: "bg-orange-500",
  };
  return <span className={`h-2 w-2 rounded-full ${styles[status]}`} />;
}

function PhaseIndicator({ phase }: { phase: string }) {
  const labels: Record<string, string> = {
    idle: "Idle",
    init: "Initializing",
    assign_task: "Assigning Tasks",
    worker_execute: "Workers Executing",
    check_progress: "Checking Progress",
    arbiter: "Arbiter Evaluating",
    hybrid_search: "Searching Cache",
    human_review: "Human Review",
    expert_answer: "Expert Answering",
    browserbase_test: "Browser Testing",
    generate_report: "Generating Report",
    expert_learn: "Learning",
    completed: "Completed",
    failed: "Failed",
  };
  return (
    <span className="rounded-full bg-zinc-800 px-3 py-1 text-zinc-300">
      {labels[phase] ?? phase}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "completed"
      ? "text-green-400"
      : status === "running"
        ? "text-yellow-400"
        : status.startsWith("failed")
          ? "text-red-400"
          : "text-zinc-400";
  return <span className={`font-medium ${color}`}>{status}</span>;
}
