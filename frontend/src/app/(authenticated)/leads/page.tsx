'use client';

import { LeadsIcon } from '@/components/ui/icons';

export default function LeadsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900">Leads</h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          Scored leads with the highest potential. Discover companies,
          trigger intelligence enrichment, and review your most promising
          prospects here.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-12">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <LeadsIcon className="h-6 w-6 text-zinc-400" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-900">
            Leads list &mdash; coming next
          </h3>
          <p className="mt-1 max-w-sm text-sm text-zinc-500">
            This page will display qualified leads sorted by intelligence
            score. Discover companies and run enrichment to generate your
            first leads.
          </p>
        </div>
      </div>
    </div>
  );
}
