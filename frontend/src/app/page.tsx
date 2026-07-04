'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';

export default function LoginPage() {
  const router = useRouter();
  const { authStatus, login } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>(
    {},
  );
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  /* ── redirect if already authenticated ── */
  useEffect(() => {
    if (authStatus === 'authenticated') {
      router.replace('/dashboard');
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
  if (authStatus === 'authenticated') {
    return null;
  }

  /* ── validation ── */
  const validate = (): boolean => {
    const next: { email?: string; password?: string } = {};
    if (!email.trim()) next.email = 'Email is required.';
    if (!password) next.password = 'Password is required.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  /* ── submit ── */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
      router.replace('/dashboard');
    } catch (err: unknown) {
      /* Map safe error messages — never expose raw backend payloads or tokens. */
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        err.response &&
        typeof err.response === 'object'
      ) {
        const status = (err.response as { status?: number }).status;
        if (status === 429) {
          setSubmitError(
            'Too many login attempts. Please try again later.',
          );
        } else if (status === 401) {
          setSubmitError('Invalid email or password.');
        } else {
          setSubmitError('Login failed. Please try again.');
        }
      } else {
        setSubmitError('Login failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm">
        {/* ── branding ── */}
        <div className="mb-10 text-center">
          <h1 className="text-[1.75rem] font-semibold tracking-tight text-zinc-900">
            Irtiqa Intelligence
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            Lead intelligence for smarter B2B outreach.
          </p>
        </div>

        {/* ── form ── */}
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          <Input
            id="login-email"
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            placeholder="you@company.com"
            autoComplete="email"
            disabled={isSubmitting}
          />

          <Input
            id="login-password"
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            placeholder="Enter your password"
            autoComplete="current-password"
            disabled={isSubmitting}
          />

          {submitError && (
            <p className="text-sm text-red-600" role="alert">
              {submitError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Spinner className="h-4 w-4" />}
            Sign in
          </Button>
        </form>
      </div>
    </main>
  );
}
