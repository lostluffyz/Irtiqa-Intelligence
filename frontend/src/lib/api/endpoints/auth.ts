import { apiClient } from '../client';
import type {
  LoginRequest,
  LoginResponse,
  RefreshTokenRequest,
  RefreshTokenResponse,
  UserResponse,
} from '../../types/api';

/**
 * Auth endpoint functions. They deliberately call the shared `apiClient` so
 * that the response interceptor (refresh on 401, escape hatches for /auth/*
 * endpoints) is applied transparently.
 *
 * These functions own the wire contract only — they do not persist or update
 * any state. Persistence and refresh orchestration live in the auth store.
 */

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', payload);
  return data;
}

export async function refresh(payload: RefreshTokenRequest): Promise<RefreshTokenResponse> {
  const { data } = await apiClient.post<RefreshTokenResponse>('/auth/refresh', payload);
  return data;
}

/**
 * Calls POST /auth/logout with the refresh token in the body. The auth store
 * is responsible for attaching the access token via the bearer header before
 * this fires (a successful call requires both).
 */
export async function logout(payload: RefreshTokenRequest): Promise<void> {
  await apiClient.post<void>('/auth/logout', payload);
}

export async function me(): Promise<UserResponse> {
  const { data } = await apiClient.get<UserResponse>('/auth/me');
  return data;
}
