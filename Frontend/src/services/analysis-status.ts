const RECOGNIZED_STATUSES = new Set([
  'complete', 'success', 'ai_generated', 'partial', 'unavailable', 'failed', 'degraded',
]);

export function normalizeTerminalAnalysisStatus(input: {
  backendStatus?: string;
  hasUsefulOutput: boolean;
  hasValidationMetadata: boolean;
  requiredStageFailed: boolean;
}): string {
  const rawStatus = input.backendStatus || '';
  if (!RECOGNIZED_STATUSES.has(rawStatus)) return input.hasUsefulOutput ? 'partial' : 'failed';

  const status = rawStatus === 'success' || rawStatus === 'ai_generated' ? 'complete'
    : rawStatus === 'degraded' || rawStatus === 'error' ? 'failed' : rawStatus;

  // Older APIs sometimes label a response failed despite including a useful
  // report, because validation metadata is missing. Keep that output visible as
  // partial unless diagnostics identify an actual required-stage failure.
  if (status === 'failed' && input.hasUsefulOutput && !input.requiredStageFailed) return 'partial';
  if (['failed', 'unavailable', 'partial'].includes(status)) return status;
  if (!input.hasValidationMetadata) return input.hasUsefulOutput ? 'partial' : 'unavailable';
  return status;
}
