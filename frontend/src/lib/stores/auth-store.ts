'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { bindAuthAccessors } from '../api/client';
import * as authApi from '../api/endpoints/auth';
import type {
  LoginRequest,
  OrganizationSummary,
  UserResponse,
} from '../types/api';

export type AuthStatus = 'initializing' | 'authenticated' | 'unauthenticated';

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserResponse | null;
  organization: OrganizationSummary | null;
  authStatus: AuthStatus;

  hasHydrated: boolean;
  bootstrapStarted: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
  bootstrap: () => Promise<void>;
  clearAuthState: () => void;
  markHydrated: () => void;
  resetBootstrap: () => void;
};

const STORAGE_KEY = 'irtiqa-auth-state';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      organization: null,
      authStatus: 'initializing',
      hasHydrated: false,
      bootstrapStarted: false,

      login: async (email: string, password: string) => {
        const payload: LoginRequest = { email, password };
        const response = await authApi.login(payload);
        set({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          user: response.user,
          organization: response.organization,
          authStatus: 'authenticated',
        });
      },

      logout: async () => {
        const { accessToken, refreshToken } = get();
        const canCallApi = Boolean(accessToken && refreshToken);
        if (canCallApi) {
          try {
            await authApi.logout({ refresh_token: refreshToken as string });
          } catch {
            // intentionally swallowed: clear local state regardless
          }
        }
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          organization: null,
          authStatus: 'unauthenticated',
        });
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        const response = await authApi.refresh({ refresh_token: refreshToken });
        set({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          authStatus: 'authenticated',
        });
      },

      bootstrap: async () => {
        const { hasHydrated, bootstrapStarted } = get();
        if (!hasHydrated || bootstrapStarted) return;
        set({ bootstrapStarted: true });
        try {
          await get().refreshAccessToken().catch(async () => {
            set({
              accessToken: null,
              refreshToken: null,
              user: null,
              organization: null,
              authStatus: 'unauthenticated',
            });
          });
          const refreshed = get();
          if (refreshed.accessToken) {
            set({ authStatus: 'authenticated' });
          } else if (!refreshed.refreshToken) {
            set({ authStatus: 'unauthenticated' });
          }
        } finally {
          if (!get().authStatus || get().authStatus === 'initializing') {
            set({ authStatus: 'unauthenticated' });
          }
        }
      },

      clearAuthState: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          organization: null,
          authStatus: 'unauthenticated',
        });
      },

      markHydrated: () => set({ hasHydrated: true }),

      resetBootstrap: () => set({ bootstrapStarted: false }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // accessToken and bootstrap gating MUST NOT survive a reload.
      partialize: (state) => ({
        refreshToken: state.refreshToken,
        user: state.user,
        organization: state.organization,
      }),
      onRehydrateStorage: () => (state) => {
        state?.markHydrated();
      },
      version: 1,
    },
  ),
);

// Wire the axios client to the store's access-token peek and refresh runner.
// The client imports this via `bindAuthAccessors`, never via a top-level
// import — that keeps the dependency graph one-directional.
bindAuthAccessors(
  () => useAuthStore.getState().accessToken,
  async () => {
    try {
      await useAuthStore.getState().refreshAccessToken();
      return useAuthStore.getState().accessToken;
    } catch {
      useAuthStore.getState().clearAuthState();
      return null;
    }
  },
);
