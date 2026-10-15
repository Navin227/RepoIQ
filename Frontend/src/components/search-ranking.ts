import type { SimilarRepo } from '../types';

/** Filter the backend-ranked list without changing its evidence-aware order. */
export function filterSearchResultsInBackendOrder(
  results: SimilarRepo[],
  predicate: (repo: SimilarRepo) => boolean,
): SimilarRepo[] {
  return results.filter(predicate);
}

/** Preserve the distinction between an assessed result, missing metadata, and failed inspection. */
export function formatEvidenceReadiness(readiness?: string, inspectionState?: string): string {
  if (readiness === 'unknown' && inspectionState === 'inspection_failed') return 'unknown (tree inspection failed)';
  if (readiness === 'unknown' && inspectionState === 'not_inspected') return 'unknown (tree not inspected)';
  if (readiness && readiness !== 'not_assessed') return readiness.replaceAll('_', ' ');
  if (inspectionState === 'inspection_failed') return 'unknown (tree inspection failed)';
  if (inspectionState === 'not_inspected') return 'unknown (tree not inspected)';
  if (inspectionState === 'inspected') return 'not assessed';
  return 'not assessed';
}
