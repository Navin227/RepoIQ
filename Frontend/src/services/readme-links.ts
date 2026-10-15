export function resolveReadmeLink(repoUrl: string, commitSha: string | undefined, readmePath: string | undefined, href: string, image = false): string {
  if (/^(https?:|mailto:|#)/i.test(href)) return href;
  if (!commitSha || !repoUrl) return href;
  try {
    const root = new URL(repoUrl).pathname.replace(/\.git$/, '').replace(/\/$/, '');
    const parsed = new URL(href, `https://local.invalid/${readmePath || 'README.md'}`);
    const path = decodeURIComponent(parsed.pathname.replace(/^\//, '')).split('/').filter(Boolean).map(encodeURIComponent).join('/');
    const suffix = `${parsed.search}${parsed.hash}`;
    return image
      ? `https://raw.githubusercontent.com${root}/${encodeURIComponent(commitSha)}/${path}${suffix}`
      : `https://github.com${root}/blob/${encodeURIComponent(commitSha)}/${path}${suffix}`;
  } catch {
    return href;
  }
}
