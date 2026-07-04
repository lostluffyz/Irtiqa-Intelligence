'use client';

import { use } from 'react';
import Link from 'next/link';
import { ChevronRightIcon, CompaniesIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';

interface CompanyDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const { id } = use(params);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-zinc-500">
        <Link href="/companies" className="hover:text-zinc-700 transition-colors">
          Companies
        </Link>
        <ChevronRightIcon className="h-3.5 w-3.5" />
        <span className="truncate text-zinc-900 font-medium">
          {id}
        </span>
      </nav>

      <div className="rounded-lg border border-zinc-200 bg-white p-12">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <CompaniesIcon className="h-6 w-6 text-zinc-400" />
          </div>
          <h2 className="mt-4 text-base font-semibold text-zinc-900">
            Company intelligence &mdash; coming next
          </h2>
          <p className="mt-1 max-w-sm text-sm text-zinc-500">
            Full company profiles with intelligence scores, technologies, intent
            signals, and outreach messages will be available here once
            enrichment is set up.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/companies">
              <Button variant="secondary" size="sm">
                Back to Companies
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
