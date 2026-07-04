import { apiClient } from '../client';
import type { CompanyList, CompanyRead } from '../../types/api';

/**
 * Returns a paginated list of companies for the current organisation.
 * Supports offset-based pagination via `limit` and `offset`.
 *
 * @param limit  Page size (default 100, range 1–500).
 * @param offset  Number of records to skip (default 0, ≥ 0).
 */
export async function listCompanies(
  limit: number = 20,
  offset: number = 0,
): Promise<CompanyList> {
  const { data } = await apiClient.get<CompanyList>('/companies', {
    params: { limit, offset },
  });
  return data;
}

/**
 * Returns a single company by its UUID.
 */
export async function getCompany(id: string): Promise<CompanyRead> {
  const { data } = await apiClient.get<CompanyRead>(`/companies/${id}`);
  return data;
}
