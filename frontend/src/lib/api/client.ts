import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

/**
 * Auth-store accessor.
 *
 * The store is set by `auth-store.ts` after the store is created. Reading via
 * this function (instead of importing the store directly) lets the Axios
 * client and the store live in the same module graph without one importing
 * the other — the store wires the accessor on initialization.
 */
type AccessTokenGetter = () => string | null;
type RefreshPromiseFactory = () => Promise<string | null>;

let getAccessToken: AccessTokenGetter = () => null;
let runRefresh: RefreshPromiseFactory = async () => null;

/**
 * Called by the auth store to expose its read-only access-token peek and
 * refresh runner. The axios client never reaches into Zustand state directly.
 */
export function bindAuthAccessors(
  tokenGetter: AccessTokenGetter,
  refreshFactory: RefreshPromiseFactory,
): void {
  getAccessToken = tokenGetter;
  runRefresh = refreshFactory;
}

const baseURL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/**
 * Refresh-safe Axios client.
 *
 * Wiring:
 *   - Request interceptor: attaches `Authorization: Bearer <accessToken>` when one exists.
 *   - Response interceptor: on 401 from a refreshable endpoint, swap the
 *     access/refresh tokens once via the auth store and retry the original
 *     request. Concurrent 401s share a single refresh promise so only one
 *     /auth/refresh call leaves the browser.
 *
 * Endpoints that must never trigger a refresh/retry:
 *   - /auth/login
 *   - /auth/register
 *   - /auth/refresh
 *   - /auth/logout
 *
 * The retry-marker is attached via `InternalAxiosRequestConfig` typing — no
 * `any`. Already-retried requests pass straight through to the error.
 */

const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

function shouldSkipRefresh(config: InternalAxiosRequestConfig | undefined): boolean {
  if (!config?.url) return true;
  return NO_REFRESH_PATHS.some((suffix) => config.url?.endsWith(suffix) || config.url?.includes(suffix));
}

export const apiClient = axios.create({
  baseURL,
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

let inFlightRefresh: Promise<string | null> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const status = error.response?.status;
    const alreadyRetried = original?._retry === true;

    if (
      status !== 401 ||
      !original ||
      alreadyRetried ||
      shouldSkipRefresh(original)
    ) {
      return Promise.reject(error);
    }

    original._retry = true;
    original.headers.set('Authorization', 'Bearer placeholder');

    try {
      if (!inFlightRefresh) {
        inFlightRefresh = runRefresh().finally(() => {
          inFlightRefresh = null;
        });
      }
      const newToken = await inFlightRefresh;
      if (!newToken) {
        return Promise.reject(error);
      }
      original.headers.set('Authorization', `Bearer ${newToken}`);
      return apiClient.request(original as AxiosRequestConfig);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  },
);
