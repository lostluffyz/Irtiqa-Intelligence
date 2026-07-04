'use client';

import { CompaniesIcon } from '@/components/ui/icons';

export default function CompaniesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900">Companies</h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          View and manage all companies discovered through searches or added
          manually. Full company profiles with intelligence scores,
          technologies, and intent signals are coming next.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-12">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <CompaniesIcon className="h-6 w-6 text-zinc-400" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-900">
            Company list &mdash; coming next
          </h3>
          <p className="mt-1 max-w-sm text-sm text-zinc-500">
            This page will show all companies with filtering, sorting, and
            detailed intelligence profiles. Run a discovery search to start
            populating your company list.
          </p>
        </div>
      </div>
    </div>
  );
}
