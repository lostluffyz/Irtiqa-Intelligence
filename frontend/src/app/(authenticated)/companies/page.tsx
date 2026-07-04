'use client';

import { useEffect, useReducer, useState } from 'react';
import Link from 'next/link';

import { CompaniesIcon } from '@/components/ui/icons';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';
import { listCompanies } from '@/lib/api/endpoints/companies';
import type { CompanyList, CompanyRead } from '@/lib/types/api';

/* ── Constants ──────────────────────────────────────────────────────────── */

const PAGE_SIZE = 20;

const STATUS_LABELS: Record<CompanyRead['status'], string> = {
  active: 'Active',
  needs_review: 'Needs Review',
  archived: 'Archived',
};

const STATUS_STYLES: Record<CompanyRead['status'], string> = {
  active:
    'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20',
  needs_review:
    'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
  archived: 'bg-zinc-50 text-zinc-600 ring-1 ring-inset ring-zinc-500/20',
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

/* ── Status badge ───────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: CompanyRead['status'] }) {
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
              {['Name', 'Domain', 'Industry', 'Status', 'Updated'].map(
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
                  <div className="h-4 w-36 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-28 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-20 rounded bg-zinc-200" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-5 w-16 rounded-full bg-zinc-200" />
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

/* ── Reducer — co-located state machine ─────────────────────────────────── */

type CompanyAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; data: CompanyList }
  | { type: 'FETCH_ERROR'; error: Error };

interface CompanyState {
  data: CompanyList | null;
  isLoading: boolean;
  error: Error | null;
}

function companyReducer(
  state: CompanyState,
  action: CompanyAction,
): CompanyState {
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

export default function CompaniesPage() {
  const [state, dispatch] = useReducer(companyReducer, {
    data: null,
    isLoading: true,
    error: null,
  });
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    dispatch({ type: 'FETCH_START' });

    listCompanies(PAGE_SIZE, offset)
      .then((result) => {
        if (!cancelled) dispatch({ type: 'FETCH_SUCCESS', data: result });
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({
            type: 'FETCH_ERROR',
            error:
              err instanceof Error
                ? err
                : new Error('Failed to load companies'),
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
          <h2 className="text-2xl font-semibold text-zinc-900">Companies</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            View and manage all companies discovered through searches or added
            manually.
          </p>
        </div>
        <TableSkeleton />
      </div>
    );
  }

  /* ── Error (no data available) ── */
  if (error && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Companies</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            View and manage all companies discovered through searches or added
            manually.
          </p>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-800">{error.message}</p>
          <p className="mt-1 text-sm text-red-600">
            Could not load the company list. Check your connection and try
            again.
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
          <h2 className="text-2xl font-semibold text-zinc-900">Companies</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            View and manage all companies discovered through searches or added
            manually.
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-12">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
              <CompaniesIcon className="h-6 w-6 text-zinc-400" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-zinc-900">
              No companies yet
            </h3>
            <p className="mt-1 max-w-sm text-sm text-zinc-500">
              Run a discovery search to find companies matching your ideal
              customer profile, or add companies manually.
            </p>
          </div>
        </div>
      </div>
    );
  }

  /* ── Data state ── */

  // TypeScript narrowing: data is non-null here because the loading, error,
  // and empty-state branches all return early above.
  const companies = data!;

  return (
    <div className="space-y-6">
      {/* Heading row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Companies</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            View and manage all companies discovered through searches or added
            manually.
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

      {/* Inline error banner (we have data but a refresh failed) */}
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
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Domain
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Industry
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Updated
                </th>
                <th className="relative px-4 py-3">
                  <span className="sr-only">View</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {companies.items.map((company) => (
                <tr
                  key={company.id}
                  className="transition-colors hover:bg-zinc-50"
                >
                  <td className="whitespace-nowrap px-4 py-3">
                    <div className="text-sm font-medium text-zinc-900">
                      {company.name}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {company.domain}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {company.industry ?? '—'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StatusBadge status={company.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="text-sm text-zinc-500">
                      {formatDate(company.updated_at)}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <Link
                      href={`/companies/${company.id}`}
                      className="text-sm font-medium text-zinc-700 transition-colors hover:text-zinc-900"
                    >
                      View
                      <span className="sr-only">, {company.name}</span>
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
          {companies.total > 0 ? (
            <>
              Showing{' '}
              <span className="font-medium text-zinc-700">{rangeStart}</span>
              {'–'}
              <span className="font-medium text-zinc-700">{rangeEnd}</span> of{' '}
              <span className="font-medium text-zinc-700">{companies.total}</span>
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
