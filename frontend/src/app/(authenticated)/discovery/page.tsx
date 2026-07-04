'use client';

import { DiscoveryIcon } from '@/components/ui/icons';

export default function DiscoveryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900">Discovery</h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          Define ideal customer profiles and run discovery searches to find
          companies that match your criteria. Monitor search results and
          trigger intelligence enrichment.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-12">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <DiscoveryIcon className="h-6 w-6 text-zinc-400" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-900">
            Discovery searches &mdash; coming next
          </h3>
          <p className="mt-1 max-w-sm text-sm text-zinc-500">
            This page will let you create and manage ICP discovery searches,
            view search results, and monitor the status of active discovery
            runs.
          </p>
        </div>
      </div>
    </div>
  );
}
