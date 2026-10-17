/** Normalize GitHub repository inputs into the canonical HTTPS repository URL. */
export function normalizeGitHubRepoInput(value: string): string {
  const cleaned = value.trim();

  if (!cleaned) return '';

  const compactRepoPattern = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  if (compactRepoPattern.test(cleaned)) {
    return `https://github.com/${cleaned.replace(/\.git$/i, '')}`;
  }

  const sshRepoPattern = /^git@github\.com:([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)(?:\.git)?$/i;
  const sshMatch = cleaned.match(sshRepoPattern);
  if (sshMatch) {
    return `https://github.com/${sshMatch[1]}`;
  }

  try {
    const parsed = new URL(cleaned);
    const hostname = parsed.hostname.toLowerCase();
    if (hostname === 'github.com' || hostname === 'www.github.com') {
      const pathParts = parsed.pathname
        .replace(/^\/+|\/+$/g, '')
        .replace(/\.git$/i, '')
        .split('/')
        .filter(Boolean);

      if (pathParts.length >= 2) {
        return `https://github.com/${pathParts[0]}/${pathParts[1]}`;
      }
    }
  } catch {
    // Leave unsupported input unchanged for the existing validation flow.
  }

  return cleaned;
}

export function getSavedRepositoryAnalysisUrl(repository: {
  fullName: string;
  url?: string;
}): string {
  return normalizeGitHubRepoInput(repository.url?.trim() || repository.fullName);
}
