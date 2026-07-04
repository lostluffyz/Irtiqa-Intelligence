'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/lib/stores/auth-store';

/**
 * Auth bootstrap — wire this once at the application root.
 *
 * Behaviour:
 * 1. Waits for Zustand persist to finish rehydrating from localStorage.
 * 2. If a refresh_token exists, tries to trade it for a new access_token
 *    by calling POST /auth/refresh.
 * 3. On success → authStatus becomes "authenticated".
 * 4. On failure (or no refresh_token) → authStatus becomes "unauthenticated".
 *
 * This component renders nothing visible. Mount it inside the root layout's
 * body so it fires on every navigation.
 */
export function AuthBootstrap() {
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const bootstrapStarted = useAuthStore((s) => s.bootstrapStarted);
  const bootstrap = useAuthStore((s) => s.bootstrap);

  useEffect(() => {
    if (hasHydrated && !bootstrapStarted) {
      // The store guards against double invocation internally, but a quick
      // client-side check keeps the effect decoupled from store internals.
      bootstrap();
    }
  }, [hasHydrated, bootstrapStarted, bootstrap]);

  return null;
}
