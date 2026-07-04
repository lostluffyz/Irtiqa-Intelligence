'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

export default function DashboardPage() {
  const router = useRouter();
  const { authStatus, user, organization, logout } = useAuthStore();

  /* ── redirect if unauthenticated ── */
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.replace('/');
    }
  }, [authStatus, router]);

  /* ── initialising state ── */
  if (authStatus === 'initializing') {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white">
        <Spinner className="h-8 w-8 text-zinc-400" />
        <span className="sr-only">Loading…</span>
      </main>
    );
  }

  /* ── redirect in flight ── */
  if (authStatus === 'unauthenticated') {
    return null;
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <h1 className="text-lg font-semibold text-zinc-900">Dashboard</h1>
          <Button variant="secondary" onClick={() => logout()}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <p className="text-xl font-semibold text-zinc-900">
            Welcome, {user?.display_name || user?.email || 'User'}
          </p>
          {organization && (
            <p className="mt-2 text-sm text-zinc-500">
              Organization: {organization.name}
            </p>
          )}
          {user?.email && (
            <p className="mt-1 text-sm text-zinc-500">{user.email}</p>
          )}
        </div>
      </main>
    </div>
  );
}
