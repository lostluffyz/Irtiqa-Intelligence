'use client';

import { use, useEffect, useReducer, useState } from 'react';
import Link from 'next/link';

import { AxiosError } from 'axios';
import { ChevronRightIcon, JobsIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { getJob } from '@/lib/api/endpoints/jobs';
import type { JobRead, JobStatus } from '@/lib/types/api';

/* ── Constants ──────────────────────────────────────────────────────────── */

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  succeeded: 'Succeeded',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const STATUS_STYLES: Record<JobStatus, string> = {
  pending: 'bg-zinc-50 text-zinc-600 ring-1 ring-inset ring-zinc-500/20',
  running: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20',
  succeeded: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20',
  failed: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20',
  cancelled: 'bg-zinc-50 text-zinc-600 ring-1 ring-inset ring-zinc-500/20',
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getUserFriendlyError(err: unknown): string {
  if (err instanceof AxiosError && err.response) {
    const detail =
      (err.response.data as { detail?: string })?.detail;
    return detail ?? 'An unexpected error occurred. Please try again.';
  }
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred. Please try again.';
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

/* ── Error message extraction ──────────────────────────────────────────── */

/**
 * Safely extract a user-safe error message from a job's last_error field.
 *
 * The backend may store errors in various formats (Python dict repr, JSON, or
 * plain text). This function only extracts a concise `message` value from
 * known structured formats. Raw payloads, organisation IDs, exception class
 * names, and stack traces are never rendered.
 *
 * Returns a safe message string, or null if none could be extracted.
 */
function parseJobErrorMessage(raw: string | null): string | null {
  if (!raw) return null;

  // Try JSON format: {"message": "..."} or {"error": {"message": "..."}}
  try {
    const parsed = JSON.parse(raw);
    const msg = parsed?.message ?? parsed?.error?.message;
    if (typeof msg === 'string' && msg.length > 0) return msg;
  } catch {
    // Not valid JSON — try Python repr next
  }

  // Try Python dict repr: {'message': '...'}
  // This handles the case where the backend does str({"code":..., "message":...})
  const pyMatch = raw.match(/'message':\s*'([^']+)'/);
  if (pyMatch && pyMatch[1].length > 0) {
    return pyMatch[1];
  }

  return null;
}

/**
 * Safely parse the payload JSON string to extract known fields.
 * Returns an object with the discovery search ID and run ID if present.
 */
function parseJobPayload(payload: string): {
  searchId: string | null;
  runId: string | null;
} {
  try {
    const parsed = JSON.parse(payload);
    const options = parsed?.options;
    return {
      searchId: options?.discovery_search_id ?? null,
      runId: options?.discovery_run_id ?? null,
    };
  } catch {
    return { searchId: null, runId: null };
  }
}

/* ── Sub-components ─────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-3 gap-4 py-3">
      <dt className="text-sm font-medium text-zinc-500">{label}</dt>
      <dd className="col-span-2 text-sm text-zinc-900">{children}</dd>
    </div>
  );
}

/* ── Loading skeleton ───────────────────────────────────────────────────── */

function DetailSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-5 w-48 rounded bg-zinc-200" />
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <div className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="grid grid-cols-3 gap-4 py-3">
              <div className="h-4 w-20 rounded bg-zinc-200" />
              <div className="h-4 w-48 rounded bg-zinc-200" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Reducer ────────────────────────────────────────────────────────────── */

type JobDetailAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; job: JobRead }
  | { type: 'FETCH_ERROR'; error: string };

interface JobDetailState {
  job: JobRead | null;
  isLoading: boolean;
  error: string | null;
}

function jobDetailReducer(
  state: JobDetailState,
  action: JobDetailAction,
): JobDetailState {
  switch (action.type) {
    case 'FETCH_START':
      return { ...state, isLoading: true, error: null };
    case 'FETCH_SUCCESS':
      return { job: action.job, isLoading: false, error: null };
    case 'FETCH_ERROR':
      return { ...state, isLoading: false, error: action.error };
  }
}

/* ── Page component ─────────────────────────────────────────────────────── */

interface JobDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function JobDetailPage({ params }: JobDetailPageProps) {
  const { id } = use(params);
  const [{ job, isLoading, error }, dispatch] = useReducer(jobDetailReducer, {
    job: null,
    isLoading: true,
    error: null,
  });
  const [copied, setCopied] = useState(false);

  const fetchJob = () => {
    dispatch({ type: 'FETCH_START' });
    getJob(id)
      .then((result) => dispatch({ type: 'FETCH_SUCCESS', job: result }))
      .catch((err) =>
        dispatch({ type: 'FETCH_ERROR', error: getUserFriendlyError(err) }),
      );
  };

  useEffect(() => {
    fetchJob();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleCopyAgentRunId = () => {
    if (!job?.agent_run_id) return;
    navigator.clipboard.writeText(job.agent_run_id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const { searchId, runId } = job ? parseJobPayload(job.payload) : { searchId: null, runId: null };
  const safeErrorMessage = job ? parseJobErrorMessage(job.last_error) : null;

  /* ── Loading ── */
  if (isLoading && !job) {
    return (
      <div className="space-y-6">
        <nav className="flex items-center gap-1 text-sm text-zinc-500">
          <Link href="/jobs" className="transition-colors hover:text-zinc-700">
            Jobs
          </Link>
          <ChevronRightIcon className="h-3.5 w-3.5" />
          <span className="truncate text-zinc-400">Loading&hellip;</span>
        </nav>
        <DetailSkeleton />
      </div>
    );
  }

  /* ── Error ── */
  if (error && !job) {
    return (
      <div className="space-y-6">
        <nav className="flex items-center gap-1 text-sm text-zinc-500">
          <Link href="/jobs" className="transition-colors hover:text-zinc-700">
            Jobs
          </Link>
          <ChevronRightIcon className="h-3.5 w-3.5" />
          <span className="truncate text-zinc-900 font-medium">
            {id.slice(0, 8)}&hellip;
          </span>
        </nav>
        <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-800">{error}</p>
          <p className="mt-1 text-sm text-red-600">
            Could not load job details.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-4"
            onClick={fetchJob}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  /* ── Not found edge case ── */
  if (!job) {
    return (
      <div className="space-y-6">
        <nav className="flex items-center gap-1 text-sm text-zinc-500">
          <Link href="/jobs" className="transition-colors hover:text-zinc-700">
            Jobs
          </Link>
          <ChevronRightIcon className="h-3.5 w-3.5" />
          <span className="truncate text-zinc-900 font-medium">Not found</span>
        </nav>
        <div className="rounded-lg border border-zinc-200 bg-white p-12 text-center">
          <div className="flex flex-col items-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
              <JobsIcon className="h-6 w-6 text-zinc-400" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-zinc-900">
              Job not found
            </h3>
            <p className="mt-1 text-sm text-zinc-500">
              This job may have been removed or the ID is invalid.
            </p>
            <Link href="/jobs">
              <Button variant="secondary" size="sm" className="mt-4">
                Back to Jobs
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-zinc-500">
        <Link href="/jobs" className="transition-colors hover:text-zinc-700">
          Jobs
        </Link>
        <ChevronRightIcon className="h-3.5 w-3.5" />
        <span className="truncate text-zinc-900 font-medium">
          {job.id.slice(0, 8)}&hellip;
        </span>
      </nav>

      {/* Status banner */}
      <div className="flex items-center gap-3">
        <StatusBadge status={job.status} />
        <span className="text-lg font-semibold text-zinc-900">
          {job.target_name}
        </span>
        {job.job_type && (
          <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-500">
            {job.job_type}
          </span>
        )}
      </div>

      {/* Detail sections */}
      <div className="space-y-6">
        {/* Timing */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h3 className="mb-1 text-sm font-semibold text-zinc-900">
            Timing
          </h3>
          <dl className="divide-y divide-zinc-100">
            <DetailRow label="Created">{formatDateTime(job.created_at)}</DetailRow>
            <DetailRow label="Scheduled">{formatDateTime(job.scheduled_at)}</DetailRow>
            <DetailRow label="Started">{formatDateTime(job.started_at)}</DetailRow>
            <DetailRow label="Completed">{formatDateTime(job.completed_at)}</DetailRow>
          </dl>
        </div>

        {/* Details */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h3 className="mb-1 text-sm font-semibold text-zinc-900">
            Details
          </h3>
          <dl className="divide-y divide-zinc-100">
            <DetailRow label="Job ID">
              <code className="break-all font-mono text-xs text-zinc-600">
                {job.id}
              </code>
            </DetailRow>
            <DetailRow label="Type">{job.job_type}</DetailRow>
            <DetailRow label="Target">{job.target_name}</DetailRow>
            <DetailRow label="Retries">
              <span>
                {job.retry_count} / {job.max_retries}
              </span>
            </DetailRow>
          </dl>
        </div>

        {/* Discovery references (from payload) */}
        {(searchId || runId) && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <h3 className="mb-1 text-sm font-semibold text-zinc-900">
              Discovery References
            </h3>
            <dl className="divide-y divide-zinc-100">
              {searchId && (
                <DetailRow label="Search ID">
                  <code className="break-all font-mono text-xs text-zinc-600">
                    {searchId}
                  </code>
                </DetailRow>
              )}
              {runId && (
                <DetailRow label="Run ID">
                  <code className="break-all font-mono text-xs text-zinc-600">
                    {runId}
                  </code>
                </DetailRow>
              )}
            </dl>
          </div>
        )}

        {/* Agent Run */}
        {job.agent_run_id && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <h3 className="mb-1 text-sm font-semibold text-zinc-900">
              Agent Run
            </h3>
            <dl className="divide-y divide-zinc-100">
              <DetailRow label="Agent Run ID">
                <div className="flex items-center gap-2">
                  <code className="break-all font-mono text-xs text-zinc-600">
                    {job.agent_run_id}
                  </code>
                  <button
                    type="button"
                    onClick={handleCopyAgentRunId}
                    className="shrink-0 rounded px-1.5 py-0.5 text-xs font-medium text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
                  >
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </DetailRow>
            </dl>
          </div>
        )}

        {/* Error */}
        {job.status === 'failed' && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6">
            <h3 className="mb-2 text-sm font-semibold text-red-900">
              Error
            </h3>
            <div className="rounded-md border border-red-200 bg-white px-4 py-3">
              <p className="whitespace-pre-wrap text-sm text-red-800">
                {safeErrorMessage ??
                  'This job could not be completed. Review the job details or try running the discovery search again.'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Back link */}
      <div className="pt-2">
        <Link href="/jobs">
          <Button variant="secondary" size="sm">
            &larr; Back to Jobs
          </Button>
        </Link>
      </div>
    </div>
  );
}
