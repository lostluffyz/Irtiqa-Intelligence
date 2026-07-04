import { apiClient } from '../client';
import type { JobList, JobRead } from '../../types/api';

/**
 * Returns a paginated list of jobs for the current organisation.
 * Supports offset-based pagination via `limit` and `offset`.
 *
 * @param limit  Page size (default 20, range 1–500).
 * @param offset  Number of records to skip (default 0, ≥ 0).
 */
export async function listJobs(
  limit: number = 20,
  offset: number = 0,
): Promise<JobList> {
  const { data } = await apiClient.get<JobList>('/jobs', {
    params: { limit, offset },
  });
  return data;
}

/**
 * Returns a single job by its UUID.
 */
export async function getJob(id: string): Promise<JobRead> {
  const { data } = await apiClient.get<JobRead>(`/jobs/${id}`);
  return data;
}
