'use client';

import { JobsIcon } from '@/components/ui/icons';

export default function JobsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900">Jobs</h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          Monitor background jobs including discovery runs and intelligence
          pipeline tasks. Track progress, review completed jobs, and retry
          or cancel as needed.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-12">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <JobsIcon className="h-6 w-6 text-zinc-400" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-900">
            Jobs list &mdash; coming next
          </h3>
          <p className="mt-1 max-w-sm text-sm text-zinc-500">
            This page will display all background jobs with status tracking,
            filtering, and the ability to cancel or retry failed jobs.
          </p>
        </div>
      </div>
    </div>
  );
}
