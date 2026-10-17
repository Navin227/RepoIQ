import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, History, LoaderCircle, RotateCw } from 'lucide-react';
import { fetchRepositoryHistory, RepositoryHistoryItem } from '../services/api';

interface HistoryPageProps {
  onOpen: (entry: RepositoryHistoryItem) => void;
  onAnalyze: (repositoryUrl: string) => void;
}

const PAGE_SIZE = 20;

function displayStatus(status?: string | null): string | null {
  if (!status) return null;
  if (['complete', 'success', 'ai_generated'].includes(status)) return 'Complete';
  if (['partial', 'degraded'].includes(status)) return 'Partial';
  if (['failed', 'error', 'unavailable'].includes(status)) return 'Failed';
  return null;
}

function formatDate(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
}

function stackPreview(entry: RepositoryHistoryItem): string[] {
  const stack = entry.analysis_result?.stack;
  const flat = stack?.flat || stack?.categories || {};
  return [...new Set(Object.values(flat).flatMap((items) =>
    Array.isArray(items) ? items.map((item) => typeof item === 'string' ? item : item?.name).filter((name): name is string => Boolean(name)) : []
  ))].slice(0, 5);
}

export default function HistoryPage({ onOpen, onAnalyze }: HistoryPageProps) {
  const [items, setItems] = useState<RepositoryHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (append: boolean) => {
    append ? setLoadingMore(true) : setLoading(true);
    setError(null);
    try {
      const page = await fetchRepositoryHistory(append ? items.length : 0, PAGE_SIZE);
      setItems((current) => append ? [...current, ...page.items] : page.items);
      setTotal(page.total);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'History could not be loaded.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [items.length]);

  useEffect(() => { void load(false); }, []); // Initial fetch; retries use the same loader.

  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 animate-fade-in" id="repository-history-page">
      <div className="border-b border-white/[0.08] pb-6 mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight text-white font-sans">Analysis History</h1>
        <p className="text-sm text-gray-400 mt-1.5 font-sans">Reopen saved repository analyses or choose to run a fresh analysis.</p>
      </div>

      {loading && items.length === 0 ? (
        <div role="status" className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-12 text-center text-sm text-gray-300">
          <LoaderCircle className="mx-auto mb-3 h-6 w-6 animate-spin text-purple-300" /> Loading analysis history…
        </div>
      ) : error && items.length === 0 ? (
        <div role="alert" className="rounded-2xl border border-red-400/20 bg-red-500/5 p-10 text-center">
          <p className="text-sm text-red-200">{error}</p>
          <button onClick={() => void load(false)} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-200 hover:bg-white/5">
            <RotateCw className="h-4 w-4" /> Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-white/[0.08] bg-white/[0.01] py-16 text-center">
          <History className="mx-auto mb-4 h-10 w-10 text-gray-500" />
          <h2 className="text-lg font-bold text-white">No analysis history yet</h2>
          <p className="mt-2 text-sm text-gray-400">Repositories you analyze will appear here.</p>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {items.map((entry) => {
              const result = entry.analysis_result;
              const status = displayStatus(result?.analysis_status);
              const timestamp = formatDate(result?.created_at || entry.created_at);
              const overview = result?.executive_overview?.one_line_summary
                || result?.executive_overview?.what_is_this_project?.[0]
                || result?.overview;
              const stack = stackPreview(entry);
              const modules = (result?.modules || []).map((module) => module.name).filter(Boolean).slice(0, 4);
              return (
                <article key={entry.id} className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5 sm:p-6 hover:border-[#8B5CF6]/30 transition-colors">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      {result ? (
                        <button onClick={() => onOpen(entry)} className="text-left text-lg font-bold text-white hover:text-purple-200 hover:underline break-all">
                          {entry.full_name}
                        </button>
                      ) : <h2 className="text-lg font-bold text-white break-all">{entry.full_name}</h2>}
                      {entry.description?.trim() && <p className="mt-1.5 text-sm leading-relaxed text-gray-400">{entry.description}</p>}
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-gray-400">
                        {entry.primary_language && <span>{entry.primary_language}</span>}
                        {typeof entry.stars === 'number' && <span>{entry.stars.toLocaleString()} stars</span>}
                        {status && <span className={status === 'Complete' ? 'text-emerald-300' : status === 'Partial' ? 'text-amber-300' : 'text-red-300'}>{status}</span>}
                        {timestamp && <time dateTime={result?.created_at || entry.created_at}>{timestamp}</time>}
                        {result?.commit_sha && <span className="font-mono">Commit {result.commit_sha.slice(0, 10)}</span>}
                      </div>
                      {overview?.trim() && <p className="mt-4 max-w-4xl text-sm leading-relaxed text-gray-300 line-clamp-2">{overview}</p>}
                      {(stack.length > 0 || modules.length > 0) && <div className="mt-3 flex flex-wrap gap-2">
                        {stack.map((technology) => <span key={`tech-${technology}`} className="rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-1 text-[11px] text-gray-300">{technology}</span>)}
                        {modules.map((module) => <span key={`module-${module}`} className="rounded-md border border-purple-500/15 bg-purple-500/5 px-2 py-1 text-[11px] text-purple-200">{module}</span>)}
                      </div>}
                      {!result && <p className="mt-4 text-sm text-amber-200">No saved analysis result is available for this repository.</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <a href={entry.github_url} target="_blank" rel="noreferrer noopener" aria-label={`Open ${entry.full_name} on GitHub`} className="rounded-lg border border-white/10 p-2 text-gray-300 hover:bg-white/5 hover:text-white">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                      {(!result || status === 'Failed') && <button onClick={() => onAnalyze(entry.github_url)} className="rounded-lg bg-purple-600 px-3 py-2 text-xs font-semibold text-white hover:bg-purple-500">{result ? 'Re-analyze' : 'Analyze'}</button>}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          {error && <div role="alert" className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-red-300">
            <span>{error}</span>
            <button onClick={() => void load(items.length > 0)} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-1.5 text-gray-200 hover:bg-white/5"><RotateCw className="h-3.5 w-3.5" />Retry</button>
          </div>}
          {items.length < total && <div className="mt-8 text-center">
            <button onClick={() => void load(true)} disabled={loadingMore} className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-5 py-2.5 text-sm text-gray-200 hover:bg-white/5 disabled:opacity-60">
              {loadingMore && <LoaderCircle className="h-4 w-4 animate-spin" />}{loadingMore ? 'Loading…' : 'Load More'}
            </button>
          </div>}
        </>
      )}
    </section>
  );
}
