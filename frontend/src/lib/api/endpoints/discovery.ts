import { apiClient } from '../client';
import type {
  DiscoverySearchCreate,
  DiscoverySearchRead,
  DiscoveryRunRead,
} from '../../types/api';

/**
 * Creates a new discovery search. The search defines the target criteria
 * (industry, keywords, geography, sources, etc.) and is persisted for
 * repeated use.
 *
 * Returns the created DiscoverySearchRead with the search's UUID.
 * Call `triggerDiscoveryRun` with that ID to start a run.
 *
 * @param payload  A fully formed DiscoverySearchCreate body.
 */
export async function createDiscoverySearch(
  payload: DiscoverySearchCreate,
): Promise<DiscoverySearchRead> {
  const { data } = await apiClient.post<DiscoverySearchRead>(
    '/discovery/searches',
    payload,
  );
  return data;
}

/**
 * Triggers an immediate discovery run for an existing search.
 * The run executes asynchronously; returns a DiscoveryRunRead with status
 * initially set to `running`.
 *
 * @param searchId  UUID of the discovery search to run.
 */
export async function triggerDiscoveryRun(
  searchId: string,
): Promise<DiscoveryRunRead> {
  const { data } = await apiClient.post<DiscoveryRunRead>(
    `/discovery/searches/${searchId}/run`,
  );
  return data;
}
