import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { resolveReadmeLink } from '../services/readme-links';
import type { Repository } from '../types';

export function RepositoryReadme({ repo }: { repo: Repository }) {
  if (!repo.readme) return <p className="text-gray-400">No README was found in this checkout.</p>;
  return (
    <article className="prose prose-invert max-w-none rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6 sm:p-8 [&_a]:text-purple-300 [&_a]:underline [&_img]:max-h-[32rem] [&_img]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:bg-black/40 [&_pre]:p-4">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            const resolved = href ? resolveReadmeLink(repo.url, repo.commitSha, repo.readmePath, href) : undefined;
            return <a {...props} href={resolved} target={resolved?.startsWith('http') ? '_blank' : undefined} rel={resolved?.startsWith('http') ? 'noreferrer noopener' : undefined}>{children}</a>;
          },
          img: ({ src, alt, ...props }) => <img {...props} src={src ? resolveReadmeLink(repo.url, repo.commitSha, repo.readmePath, src, true) : undefined} alt={alt || ''} />,
        }}
      >
        {repo.readme}
      </ReactMarkdown>
    </article>
  );
}
