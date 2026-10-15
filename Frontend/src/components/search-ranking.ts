import type { SimilarRepo } from '../types';

/** Filter the backend-ranked list without changing its evidence-aware order. */
export function filterSearchResultsInBackendOrder(
  results: SimilarRepo[],
  predicate: (repo: SimilarRepo) => boolean,
): SimilarRepo[] {
  return results.filter(predicate);
}
