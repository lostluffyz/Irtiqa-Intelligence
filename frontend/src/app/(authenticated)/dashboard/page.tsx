'use client';

import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import {
  CompaniesIcon,
  LeadsIcon,
  JobsIcon,
  ChevronRightIcon,
} from '@/components/ui/icons';
import Link from 'next/link';

/* ── Stat card ──────────────────────────────────────────────────────────── */

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-100">
          <Icon className="h-5 w-5 text-zinc-500" />
        </div>
        <div>
          <p className="text-sm text-zinc-500">{label}</p>
          <p className="text-2xl font-semibold text-zinc-900">{value}</p>
        </div>
      </div>
    </div>
  );
}

/* ── Dashboard page ─────────────────────────────────────────────────────── */

export default function DashboardPage() {
  const { user, organization } = useAuthStore();

  return (
    <div className="space-y-8">
      {/* Greeting */}
      <div>
        <p className="text-sm text-zinc-500">
          {organization?.name && `${organization.name} / `}Dashboard
        </p>
        <h2 className="mt-1 text-2xl font-semibold text-zinc-900">
          Welcome, {user?.display_name || user?.email || 'User'}
        </h2>
        <p className="mt-2 max-w-xl text-sm text-zinc-500">
          Lead intelligence will appear here as companies are discovered and
          scored. Start by defining a discovery search or review your active
          jobs.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard icon={CompaniesIcon} label="Companies" value="—" />
        <StatCard icon={LeadsIcon} label="Qualified Leads" value="—" />
        <StatCard icon={JobsIcon} label="Active Jobs" value="—" />
      </div>

      {/* What's next */}
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <h3 className="text-base font-semibold text-zinc-900">What&rsquo;s next</h3>
        <p className="mt-1 text-sm text-zinc-500">
          Get started by defining your ideal customer profile, then discover
          companies that match.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/companies">
            <Button variant="primary" size="md">
              Browse Companies
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/discovery">
            <Button variant="secondary" size="md">
              New Discovery Search
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
