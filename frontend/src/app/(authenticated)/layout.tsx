'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import {
  DashboardIcon,
  CompaniesIcon,
  LeadsIcon,
  DiscoveryIcon,
  JobsIcon,
  MenuIcon,
  CloseIcon,
  SignOutIcon,
} from '@/components/ui/icons';

/* ── Navigation config ─────────────────────────────────────────────────── */

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: DashboardIcon },
  { label: 'Companies', href: '/companies', icon: CompaniesIcon },
  { label: 'Leads', href: '/leads', icon: LeadsIcon },
  { label: 'Discovery', href: '/discovery', icon: DiscoveryIcon },
  { label: 'Jobs', href: '/jobs', icon: JobsIcon },
];

/* ── Page title helper ──────────────────────────────────────────────────── */

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/companies': 'Companies',
  '/leads': 'Leads',
  '/discovery': 'Discovery',
  '/jobs': 'Jobs',
};

function pageTitle(pathname: string): string {
  const base = '/' + pathname.split('/')[1];
  return PAGE_TITLES[base] || 'Dashboard';
}

/* ── Loading screen ─────────────────────────────────────────────────────── */

function LoadingScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white">
      <Spinner className="h-8 w-8 text-zinc-400" />
      <span className="sr-only">Loading…</span>
    </main>
  );
}

/* ── Sidebar content (shared by desktop sidebar + mobile drawer) ────────── */

function SidebarContent({
  pathname,
  onNavClick,
}: {
  pathname: string;
  onNavClick?: () => void;
}) {
  const { user, organization, logout } = useAuthStore();

  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center gap-2 border-b border-zinc-200 px-6">
        <span className="text-lg font-semibold tracking-tight text-zinc-900">
          Irtiqa Intelligence
        </span>
        {organization && (
          <span className="hidden rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] font-medium text-zinc-500 lg:inline-block">
            {organization.name}
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Sidebar">
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavClick}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-zinc-100 text-zinc-900'
                      : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700'
                  }`}
                >
                  <item.icon
                    className={`h-5 w-5 shrink-0 ${
                      isActive ? 'text-zinc-900' : 'text-zinc-400'
                    }`}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User area */}
      <div className="shrink-0 border-t border-zinc-200 px-4 py-4">
        <div className="mb-3 truncate text-sm text-zinc-500">
          {user?.display_name || user?.email || 'User'}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-zinc-500"
          onClick={() => logout()}
          aria-label="Sign out"
        >
          <SignOutIcon className="h-4 w-4 shrink-0" />
          Sign out
        </Button>
      </div>
    </div>
  );
}

/* ── Main layout ────────────────────────────────────────────────────────── */

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { authStatus, organization } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  /* ── auth guard ── */
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.replace('/');
    }
  }, [authStatus, router]);

  /* ── lock body scroll when mobile drawer is open ── */
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  /* ── close mobile drawer on Escape ── */
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [mobileMenuOpen]);

  /* ── loading / redirect states ── */
  if (authStatus === 'initializing') {
    return <LoadingScreen />;
  }

  if (authStatus === 'unauthenticated') {
    return null; /* redirect in flight */
  }

  const title = pageTitle(pathname);

  return (
    <div className="flex min-h-screen bg-zinc-50">
      {/*
       * Desktop sidebar — always visible at lg+.
       * Using two separate elements (sidebar + drawer) rather than a
       * responsive toggle so React never re-mounts the desktop nav.
       */}
      <aside className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex flex-col bg-white shadow-sm ring-1 ring-zinc-200 h-full">
          <SidebarContent pathname={pathname} />
        </div>
      </aside>

      {/* Mobile slide-over drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
          {/* Panel */}
          <div className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-white shadow-xl">
            <div className="flex h-16 shrink-0 items-center justify-end border-b border-zinc-200 px-4">
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500"
                aria-label="Close menu"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>
            <SidebarContent
              pathname={pathname}
              onNavClick={() => setMobileMenuOpen(false)}
            />
          </div>
        </div>
      )}

      {/*
       * Main area — offset for sidebar on desktop via lg:pl-64.
       * The top bar is sticky so it stays put on long content pages.
       */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-4 sm:px-6">
          {/* Mobile menu trigger */}
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 lg:hidden"
            aria-label="Open menu"
          >
            <MenuIcon className="h-5 w-5" />
          </button>

          <h1 className="text-lg font-semibold text-zinc-900">{title}</h1>

          <div className="flex-1" />

          {/* Organization name — visible on desktop */}
          {organization?.name && (
            <span className="hidden text-sm text-zinc-500 sm:inline">
              {organization.name}
            </span>
          )}
        </header>

        <main className="flex-1">
          <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
