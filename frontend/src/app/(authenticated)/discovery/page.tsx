'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';

import { AxiosError } from 'axios';
import { ChevronRightIcon } from '@/components/ui/icons';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import {
  createDiscoverySearch,
  triggerDiscoveryRun,
} from '@/lib/api/endpoints/discovery';
import type {
  DiscoveryRunRead,
  DiscoverySearchRead,
} from '@/lib/types/api';

/* ── Constants ──────────────────────────────────────────────────────────── */

const SOURCE_OPTIONS = [
  { value: 'sec_edgar', label: 'SEC EDGAR' },
  { value: 'google_news_rss', label: 'Google News' },
  { value: 'opencorporates', label: 'OpenCorporates' },
] as const;

const DEFAULT_SOURCES = ['sec_edgar', 'google_news_rss'];

/* ── Submit status machine ──────────────────────────────────────────────── */

type SubmitStatus =
  | { type: 'idle' }
  | { type: 'submitting' }
  | {
      type: 'search_created';
      search: DiscoverySearchRead;
    }
  | {
      type: 'completed';
      search: DiscoverySearchRead;
      run: DiscoveryRunRead;
    }
  | {
      type: 'run_failed';
      search: DiscoverySearchRead;
      runError: string;
    }
  | { type: 'error'; message: string };

/* ── Helpers ────────────────────────────────────────────────────────────── */

/**
 * Extract a user-friendly error message from a failed API call.
 * Follows the same pattern as the companies page — reads `detail` from
 * the JSON response body when available.
 */
function getUserFriendlyError(err: unknown): string {
  if (err instanceof AxiosError && err.response) {
    const detail = (err.response.data as { detail?: string })?.detail;
    if (err.response.status === 403) {
      return (
        detail ??
        "You don't have permission to create discovery searches in this organization."
      );
    }
    return detail ?? 'An unexpected error occurred. Please try again.';
  }
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred. Please try again.';
}

/* ── Source checkbox sub-component ──────────────────────────────────────── */

function SourceCheckbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-zinc-200 px-3 py-2.5 text-sm transition-colors hover:bg-zinc-50 has-[:checked]:border-zinc-900 has-[:checked]:bg-zinc-50">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
      />
      <span className="font-medium text-zinc-900">{label}</span>
    </label>
  );
}

/* ── Success icon ───────────────────────────────────────────────────────── */

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

/* ── Warning icon ───────────────────────────────────────────────────────── */

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v2m0 4h.01"
      />
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

/* ── Page component ─────────────────────────────────────────────────────── */

export default function DiscoveryPage() {
  /* ── Form fields ── */
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [industry, setIndustry] = useState('');
  const [geography, setGeography] = useState('');
  const [keywordsStr, setKeywordsStr] = useState('');
  const [selectedSources, setSelectedSources] =
    useState<string[]>(DEFAULT_SOURCES);

  /* ── Validation errors ── */
  const [nameError, setNameError] = useState('');
  const [industryError, setIndustryError] = useState('');
  const [keywordsError, setKeywordsError] = useState('');

  /* ── Submit machine ── */
  const [status, setStatus] = useState<SubmitStatus>({ type: 'idle' });

  /* ── Validation ── */
  const validate = useCallback((): boolean => {
    let valid = true;

    if (!name.trim()) {
      setNameError('Search name is required.');
      valid = false;
    } else {
      setNameError('');
    }

    if (!industry.trim()) {
      setIndustryError('Industry is required.');
      valid = false;
    } else {
      setIndustryError('');
    }

    const parsed = keywordsStr
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);
    if (parsed.length === 0) {
      setKeywordsError('At least one keyword is required.');
      valid = false;
    } else {
      setKeywordsError('');
    }

    return valid;
  }, [name, industry, keywordsStr]);

  /* ── Submit handler ── */
  const handleSubmit = useCallback(async () => {
    if (!validate()) return;

    setStatus({ type: 'submitting' });

    const keywords = keywordsStr
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);
    const sources =
      selectedSources.length > 0 ? selectedSources : undefined;

    try {
      const search = await createDiscoverySearch({
        name: name.trim(),
        description: description.trim() || null,
        criteria: {
          industry: industry.trim(),
          geography: geography.trim() || null,
          keywords,
          sources,
        },
      });

      /* Search created — now trigger a run */
      try {
        const run = await triggerDiscoveryRun(search.id);
        setStatus({ type: 'completed', search, run });
      } catch (runErr) {
        setStatus({
          type: 'run_failed',
          search,
          runError: getUserFriendlyError(runErr),
        });
      }
    } catch (err) {
      setStatus({ type: 'error', message: getUserFriendlyError(err) });
    }
  }, [
    name,
    description,
    industry,
    geography,
    keywordsStr,
    selectedSources,
    validate,
  ]);

  /* ── Source toggle ── */
  const toggleSource = (value: string) => {
    setSelectedSources((prev) =>
      prev.includes(value)
        ? prev.filter((s) => s !== value)
        : [...prev, value],
    );
  };

  /* ── Full reset (back to form) ── */
  const resetForm = () => {
    setName('');
    setDescription('');
    setIndustry('');
    setGeography('');
    setKeywordsStr('');
    setSelectedSources(DEFAULT_SOURCES);
    setNameError('');
    setIndustryError('');
    setKeywordsError('');
    setStatus({ type: 'idle' });
  };

  /* ════════════════════════════════════════════════════════════════
   * SUBMITTING
   * ════════════════════════════════════════════════════════════════ */
  if (status.type === 'submitting') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Discovery</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Creating discovery search and starting a run&hellip;
          </p>
        </div>
        <div className="flex items-center justify-center rounded-lg border border-zinc-200 bg-white p-16">
          <div className="flex flex-col items-center gap-4">
            <Spinner className="h-8 w-8 text-zinc-400" />
            <p className="text-sm text-zinc-500">
              Please wait while the search is created and the discovery run
              starts.
            </p>
          </div>
        </div>
      </div>
    );
  }

  /* ════════════════════════════════════════════════════════════════
   * SUCCESS / PARTIAL SUCCESS
   * ════════════════════════════════════════════════════════════════ */

  const isSuccessState =
    status.type === 'completed' ||
    status.type === 'search_created' ||
    status.type === 'run_failed';

  if (isSuccessState) {
    const { search } = status;
    const run = status.type === 'completed' ? status.run : null;
    const runError = status.type === 'run_failed' ? status.runError : null;

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Discovery</h2>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-8">
          {/* Both search and run succeeded */}
          {status.type === 'completed' && (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100">
                <CheckCircleIcon className="h-6 w-6 text-emerald-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-zinc-900">
                Discovery search created and running
              </h3>
              <p className="mt-2 text-sm text-zinc-500">
                Your search &ldquo;{search.name}&rdquo; has been created and a
                discovery run has started. You can monitor its progress on the
                Jobs page.
              </p>
              {run && (
                <div className="mt-4 inline-flex items-center gap-2 rounded-md bg-zinc-50 px-4 py-2 text-sm text-zinc-600">
                  <span>Run ID:</span>
                  <code className="font-mono text-xs text-zinc-500">
                    {run.id}
                  </code>
                </div>
              )}
            </div>
          )}

          {/* Search created but run couldn't be triggered */}
          {status.type === 'run_failed' && (
            <>
              <div className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
                  <WarningIcon className="h-6 w-6 text-amber-600" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-zinc-900">
                  Search created, but run failed to start
                </h3>
                <p className="mt-2 text-sm text-zinc-500">
                  Your search &ldquo;{search.name}&rdquo; was saved, but the
                  discovery run could not be started. You can trigger it
                  manually.
                </p>
              </div>
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-sm text-amber-800">{runError}</p>
              </div>
            </>
          )}

          {/* Search created, skipped the run step (no run endpoint used) */}
          {status.type === 'search_created' && (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                <CheckCircleIcon className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-zinc-900">
                Discovery search created
              </h3>
              <p className="mt-2 text-sm text-zinc-500">
                Your search &ldquo;{search.name}&rdquo; has been created.
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="mt-8 flex justify-center gap-3">
            <Button variant="secondary" size="md" onClick={resetForm}>
              New Search
            </Button>
            <Link href="/jobs">
              <Button variant="primary" size="md">
                View Jobs
                <ChevronRightIcon className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  /* ════════════════════════════════════════════════════════════════
   * ERROR (no search created)
   * ════════════════════════════════════════════════════════════════ */

  if (status.type === 'error') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900">Discovery</h2>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">
            Define ideal customer profiles and run discovery searches to find
            companies that match your criteria.
          </p>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-800">
            {status.message}
          </p>
          <p className="mt-1 text-sm text-red-600">
            Could not create the discovery search. Check your connection and try
            again.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-4"
            onClick={() => setStatus({ type: 'idle' })}
          >
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  /* ════════════════════════════════════════════════════════════════
   * FORM (idle)
   * ════════════════════════════════════════════════════════════════ */

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900">
          New Discovery Search
        </h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          Define an ideal customer profile to find matching companies. Searches
          are saved and can be re-run later.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
          className="space-y-6"
        >
          {/* ── Search details ── */}
          <fieldset>
            <legend className="text-base font-semibold text-zinc-900">
              Search details
            </legend>
            <div className="mt-4 space-y-4">
              <Input
                label="Search name"
                placeholder="e.g. Fintech Series A targets"
                value={name}
                onChange={(e) => setName(e.target.value)}
                error={nameError}
                maxLength={255}
                required
              />
              <Input
                label="Description (optional)"
                placeholder="Add notes about what you are looking for"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </fieldset>

          {/* ── Target criteria ── */}
          <fieldset>
            <legend className="text-base font-semibold text-zinc-900">
              Target criteria
            </legend>
            <div className="mt-4 space-y-4">
              <Input
                label="Industry"
                placeholder="e.g. Financial Services"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                error={industryError}
                maxLength={150}
                required
              />
              <Input
                label="Geography (optional)"
                placeholder="e.g. United States"
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                maxLength={150}
              />
              <Input
                label="Keywords"
                placeholder="e.g. fintech, payments, banking"
                value={keywordsStr}
                onChange={(e) => setKeywordsStr(e.target.value)}
                error={keywordsError}
                required
              />
              <p className="-mt-2 text-xs text-zinc-400">
                Separate multiple keywords with commas.
              </p>
            </div>
          </fieldset>

          {/* ── Data sources ── */}
          <fieldset>
            <legend className="text-base font-semibold text-zinc-900">
              Data sources
            </legend>
            <p className="mt-1 text-sm text-zinc-500">
              Choose which sources to search. At least one is recommended.
            </p>
            <div className="mt-3 space-y-2">
              {SOURCE_OPTIONS.map((source) => (
                <SourceCheckbox
                  key={source.value}
                  label={source.label}
                  checked={selectedSources.includes(source.value)}
                  onChange={() => toggleSource(source.value)}
                />
              ))}
            </div>
          </fieldset>

          {/* ── Submit ── */}
          <div className="flex justify-end gap-3 border-t border-zinc-200 pt-6">
            <Link href="/dashboard">
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </Link>
            <Button type="submit" variant="primary">
              Create &amp; Run
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
