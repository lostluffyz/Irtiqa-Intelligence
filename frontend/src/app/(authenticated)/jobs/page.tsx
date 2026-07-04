'use client';

import { useEffect, useReducer, useState } from 'react';
import Link from 'next/link';

import { AxiosError } from 'axios';
import { JobsIcon } from '@/components/ui/icons';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';
import { listJobs } from '@/lib/api/endpoints/jobs';
import type { JobList, JobStatus } from '@/lib/types/api';

/* ── Constants ──────────────────────────────────────────────────────────── */

const PAGE_SIZE = 20;

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

const TARGET_LABELS: Record<string, string> = {
  discovery_pipeline: 'Discovery Pipeline',
  intelligence_pipeline: 'Intelligence Pipeline',
  score_refresh: 'Score Refresh',
};

function targetLabel(name: string): string {
  return TARGET_LABELS[name] || name;
}

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

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function shortId(id: string): string {
  if (id.length <= 8) return id;
  return id.slice(0, 8) + '…';
}

/* ── Status badge ───────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

/* ── Loading skeleton ───────────────────────────────────────────────────── */

function TableSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-zinc-200">
          <thead className="bg-zinc-50">
            <tr>
              {['Type', 'Status', 'Created', 'Started', 'Completed'].map(
                (h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500"
                  >
                    {h}
                  </th>
                ),
              )}
              <th className="relative px-4 py-3">
                <span className="sr-only">View</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="animate-pulse">
                <td className="px-4 py-3">
                  <div className="h-4 w-28 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-5 w-16 rounded-full bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-24 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-24 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-24 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-12 rounded bg-zinc-200" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Reducer ────────────────────────────────────────────────────────────── */

type JobAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; data: JobList }
  | { type: 'FETCH_ERROR'; error: Error };

interface JobState {
  data: JobList | null;
  isLoading: boolean;
  error: Error | null;
}

function jobReducer(state: JobState, action: JobAction): JobState {
  switch (action.type) {
    case 'FETCH_START':
      return { ...state, isLoading: true, error: null };
    case 'FETCH_SUCCESS':
      return { data: action.data, isLoading: false, error: null };
    case 'FETCH_ERROR':
      return { ...state, isLoading: false, error: action.error };
  }
}

/* ── Page component ─────────────────────────────────────────────────────── */

export default function JobsPage() {
  const [state, dispatch] = useReducer(jobReducer, {
    data: null,
    isLoading: true,
    error: null,
  });
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    dispatch({ type: 'FETCH_START' });

    listJobs(PAGE_SIZE, offset)
      .then((result) => {
        if (!cancelled) dispatch({ type: 'FETCH_SUCCESS', data: result });
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({
            type: 'FETCH_ERROR',
            error: new Error(getUserFriendlyError(err)),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [offset, refreshKey]);

  const { data, isLoading, error } = state;

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const hasPrevious = offset > 0;
  const hasNext = data !== null && offset + PAGE_SIZE < data.total;
  const rangeStart = data !== null && data.total > 0 ? offset + 1 : 0;
  const rangeEnd =
    data !== null ? Math.min(offset + PAGE_SIZE, data.total) : 0;

  /* ── Initial loading (no data yet) ── */
  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Jobs</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Monitor background jobs including discovery runs and intelligence
            pipeline tasks.
          </p>
        </div>
        <TableSkeleton />
      </div>
    );
  }

  /* ── Error (no data) ── */
  if (error && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Jobs</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Monitor background jobs including discovery runs and intelligence
            pipeline tasks.
          </p>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-800">{error.message}</p>
          <p className="mt-1 text-sm text-red-600">
            Could not load the job list. Check your connection and try again.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-4"
            onClick={handleRefresh}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  /* ── Empty state ── */
  if (data && data.items.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Jobs</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Monitor background jobs including discovery runs and intelligence
            pipeline tasks.
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-12">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
              <JobsIcon className="h-6 w-6 text-zinc-400" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-zinc-900">
              No jobs yet
            </h3>
            <p className="mt-1 max-w-sm text-sm text-zinc-500">
              Jobs are created automatically when you start a discovery search
              or trigger an intelligence pipeline run.
            </p>
            <Link href="/discovery">
              <Button variant="primary" size="sm" className="mt-4">
                New Discovery Search
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // TypeScript narrowing
  const jobs = data!;

  return (
    <div className="space-y-6">
      {/* Heading row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Jobs</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Monitor background jobs including discovery runs and intelligence
            pipeline tasks.
          </p>
        </div>
        <div className="shrink-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Spinner className="h-4 w-4" />
                Refreshing&hellip;
              </>
            ) : (
              'Refresh'
            )}
          </Button>
        </div>
      </div>

      {/* Inline error banner (refresh failed but we have previous data) */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-red-800">{error.message}</p>
            <Button
              variant="ghost"
              size="sm"
              className="text-red-700 hover:bg-red-100"
              onClick={handleRefresh}
            >
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-zinc-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200">
            <thead className="bg-zinc-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Created
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Started
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Completed
                </th>
                <th className="relative px-4 py-3">
                  <span className="sr-only">View</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {jobs.items.map((job) => (
                <tr
                  key={job.id}
                  className="transition-colors hover:bg-zinc-50"
                >
                  <td className="whitespace-nowrap px-4 py-3">
                    <div className="text-sm font-medium text-zinc-900">
                      {targetLabel(job.target_name)}
                    </div>
                    <div className="text-xs text-zinc-400">
                      {shortId(job.id)}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {formatDateTime(job.created_at)}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {job.started_at ? formatDateTime(job.started_at) : '—'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {job.completed_at ? formatDateTime(job.completed_at) : '—'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-sm font-medium text-zinc-700 transition-colors hover:text-zinc-900"
                    >
                      View
                      <span className="sr-only">, {shortId(job.id)} job</span>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">
          {jobs.total > 0 ? (
            <>
              Showing{' '}
              <span className="font-medium text-zinc-700">{rangeStart}</span>
              {'–'}
              <span className="font-medium text-zinc-700">{rangeEnd}</span> of{' '}
              <span className="font-medium text-zinc-700">{jobs.total}</span>
            </>
          ) : (
            'No results'
          )}
        </p>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!hasPrevious || isLoading}
            onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!hasNext || isLoading}
            onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
