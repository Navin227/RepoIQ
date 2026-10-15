import React, { useState, useEffect } from 'react';
import { 
  Star, GitFork, BookMarked, Terminal, SlidersHorizontal, 
  ChevronRight, Check, Search, Sparkles,
  Clock, Trash2, ChevronDown, ArrowRight 
} from 'lucide-react';
import { SimilarRepo } from '../types';
import { filterSearchResultsInBackendOrder } from './search-ranking';

interface SearchResultsProps {
  query: string;
  results: SimilarRepo[];
  isLoading: boolean;
  error: string | null;
  analyzingRepoUrl: string | null;
  analyzeMessageByUrl: Record<string, string>;
  onAnalyze: (repoUrl: string) => void;
  onBackToHome: () => void;
  onSearch: (query: string) => void;
  apiAvailable: boolean;
}

export default function SearchResults({ query, results, isLoading, error, analyzingRepoUrl, analyzeMessageByUrl, onAnalyze, onBackToHome, onSearch, apiAvailable }: SearchResultsProps) {
  const [selectedLanguage, setSelectedLanguage] = useState<string>('All');

  // Intelligent local search bar states
  const [localQuery, setLocalQuery] = useState(query && query !== 'Featured Repositories' ? query : '');
  
  // Custom recent search history store
  const [recentSearchHistory, setRecentSearchHistory] = useState<string[]>([
    'file sharing platform',
    'kubernetes dashboard',
    'ai chatbot',
    'supabase self-hosted instructions',
    'https://github.com/microsoft/TypeScript'
  ]);
  const [isHistoryExpanded, setIsHistoryExpanded] = useState<boolean>(true);

  // Sync prop changes back to local query state
  useEffect(() => {
    if (query && query !== 'Featured Repositories') {
      setLocalQuery(query);
    } else {
      setLocalQuery('');
    }
  }, [query]);

  // Suggested clickable chips
  const suggestedChips = [
    'file sharing platform',
    'kubernetes dashboard',
    'gofile clone',
    'ai code assistant',
    'video processing platform'
  ];

  // Helper to prepend search elements securely
  const addToHistory = (text: string) => {
    setRecentSearchHistory(prev => {
      const filtered = prev.filter(item => item.toLowerCase() !== text.toLowerCase());
      return [text, ...filtered].slice(0, 8); // Keep last 8 unique items
    });
  };

  const removeFromHistory = (text: string) => {
    setRecentSearchHistory(prev => prev.filter(item => item !== text));
  };

  const handleLocalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!localQuery.trim()) return;

    const trimmed = localQuery.trim();
    addToHistory(trimmed);

    // Smart Router: check if input matches GitHub URL or repository coordinates e.g. vercel/next.js
    onSearch(trimmed);
  };

  const handleChipClick = (value: string) => {
    setLocalQuery(value);
    addToHistory(value);

    onSearch(value);
  };

  // Extract unique languages for filter selection
  const uniqueLanguages = ['All', ...Array.from(new Set(results.map(r => r.language).filter(Boolean)))];

  // Apply filters
  const filteredResults = filterSearchResultsInBackendOrder(results, repo => {
    if (selectedLanguage !== 'All' && repo.language !== selectedLanguage) return false;
    return true;
  });

  // Preserve the evidence-aware ordering returned by the backend.

  // Language colors mapping
  const languageColors: Record<string, string> = {
    "TypeScript": "bg-blue-400",
    "JavaScript": "bg-yellow-400",
    "Go": "bg-teal-400",
    "Python": "bg-indigo-400",
    "Rust": "bg-orange-500",
    "C++": "bg-pink-500",
    "HTML": "bg-red-500",
    "CSS": "bg-purple-400"
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10" id="search-results-page">
      
      {/* 1. Breadcrumb / Top Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-white/[0.08] pb-6 mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-500 font-mono">
            <button onClick={onBackToHome} className="hover:text-white transition-colors cursor-pointer bg-transparent border-0 p-0 text-left">RepoIQ</button>
            <ChevronRight className="h-3 w-3" />
            <span>Explore Dashboard</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mt-2 font-sans" id="results-headline">
            Results for: <span className="bg-gradient-to-r from-[#8B5CF6] to-pink-500 bg-clip-text text-transparent font-mono">&quot;{query}&quot;</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Found {filteredResults.length} repositories matching your request
          </p>
        </div>

        {/* Back navigation shortcut */}
        <button
          onClick={onBackToHome}
          className="px-4 py-2 rounded-xl bg-white/[0.03] text-sm text-gray-300 border border-white/[0.06] hover:bg-white/[0.06] transition-all cursor-pointer"
        >
          &larr; Back to Search
        </button>
      </div>

      {/* 2. Primary Large Intelligent Search Bar container focused area */}
      <div className="mb-12 max-w-4xl mx-auto" id="explore-search-glassmorphism">
        <form 
          onSubmit={handleLocalSubmit}
          className="relative flex items-center p-2 rounded-2xl bg-white/[0.03] backdrop-blur-md border border-white/[0.08] focus-within:border-[#8B5CF6]/50 focus-within:ring-1 focus-within:ring-[#8B5CF6]/30 shadow-[0_0_40px_rgba(139,92,246,0.12)] transition-all duration-300"
        >
          <div className="flex-1 flex items-center pl-3">
            <Search className="h-5 w-5 text-gray-500 mr-3 shrink-0" />
            <input
              type="text"
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              placeholder="Search project ideas or paste a GitHub repository URL..."
              className="w-full bg-transparent text-white placeholder-gray-500 py-3 text-base font-sans outline-none focus:ring-0 focus:outline-none"
              id="explore-search-input"
              disabled={!apiAvailable}
            />
          </div>
          
          <button
            type="submit"
            disabled={!apiAvailable}
            className="inline-flex items-center justify-center px-6 py-3 rounded-xl bg-gradient-to-r from-[#8B5CF6] to-purple-700 hover:from-purple-500 hover:to-purple-600 font-semibold text-white shadow-lg transition-all duration-200 cursor-pointer text-sm shrink-0"
            id="explore-search-submit"
          >
            Analyze Project
            <ArrowRight className="ml-2 h-4 w-4" />
          </button>
        </form>

        {/* Suggested interactive chips */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <span className="text-xs text-gray-500 font-mono">Suggestions:</span>
          {suggestedChips.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleChipClick(chip)}
              disabled={!apiAvailable}
              className="px-3.5 py-1.5 text-xs rounded-xl bg-white/[0.02] text-gray-300 border border-white/[0.05] hover:border-[#8B5CF6]/40 hover:bg-[#8B5CF6]/5 transition-all cursor-pointer font-sans"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* 3. Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        {/* Left Sidebar Filtering & History Panels */}
        <div className="space-y-6">
          
          {/* Languages Filter */}
          <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-5">
            <div className="flex items-center gap-2 font-bold text-white text-sm tracking-wide font-sans mb-4 uppercase">
              <SlidersHorizontal className="h-4 w-4 text-[#8B5CF6]" />
              Filter Languages
            </div>
            
            <div className="space-y-1.5">
              {uniqueLanguages.map((lang) => (
                <button
                  key={lang}
                  onClick={() => setSelectedLanguage(lang)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all cursor-pointer ${
                    selectedLanguage === lang
                      ? 'bg-[#8B5CF6]/15 text-white font-semibold border-l-2 border-[#8B5CF6]'
                      : 'text-gray-400 hover:text-white hover:bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${languageColors[lang] || 'bg-gray-500'}`} />
                    <span>{lang}</span>
                  </div>
                  {selectedLanguage === lang && <Check className="h-3 w-3 text-[#8B5CF6]" />}
                </button>
              ))}
            </div>
          </div>

          {/* Collapsible Recent Search History Panel */}
          <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] overflow-hidden" id="explore-history-panel">
            <button 
              onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
              className="w-full flex items-center justify-between px-5 py-4 font-bold text-white text-sm tracking-wide font-sans uppercase bg-white/[0.01] hover:bg-white/[0.03] transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-[#8B5CF6]" />
                Recent History
              </div>
              <ChevronDown className={`h-4 w-4 text-gray-500 transition-transform duration-200 ${isHistoryExpanded ? 'rotate-180' : ''}`} />
            </button>
            
            {isHistoryExpanded && (
              <div className="p-4 space-y-2.5 border-t border-white/[0.04]">
                {recentSearchHistory.length === 0 ? (
                  <p className="text-xs text-gray-500 text-center py-2 font-mono">No searches performed.</p>
                ) : (
                  <div className="space-y-1 max-h-48 overflow-y-auto scrollbar-none">
                    {recentSearchHistory.map((item, index) => (
                      <div 
                        key={index}
                        className="flex items-center justify-between group/history rounded-lg hover:bg-white/[0.02] px-2 py-1 transition-colors"
                      >
                        <button
                          onClick={() => handleChipClick(item)}
                          className="flex-1 text-left text-xs font-mono text-gray-400 hover:text-[#8B5CF6] truncate cursor-pointer mr-2 pr-1"
                          title={item}
                        >
                          {item}
                        </button>
                        <button
                          onClick={() => removeFromHistory(item)}
                          className="p-1 rounded text-gray-600 hover:text-red-400 hover:bg-white/[0.05] opacity-0 group-hover/history:opacity-100 transition-opacity cursor-pointer"
                          title="Delete"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                
                {recentSearchHistory.length > 0 && (
                  <button
                    onClick={() => setRecentSearchHistory([])}
                    className="w-full text-center text-[10px] uppercase font-mono text-gray-500 hover:text-white pt-2 border-t border-white/[0.02] cursor-pointer block bg-transparent border-0"
                  >
                    Clear History
                  </button>
                )}
              </div>
            )}
          </div>

        </div>

        {/* Main List Area (3/4 grid width) */}
        <div className="lg:col-span-3 space-y-4">
          {isLoading ? (
            <div className="rounded-2xl border border-dashed border-white/[0.08] p-12 text-center">
              <Sparkles className="h-10 w-10 text-gray-500 mx-auto mb-4" />
              <h3 className="text-base font-bold text-white font-sans">Searching GitHub repositories</h3>
              <p className="text-xs text-gray-400 mt-1">Fetching real repositories from GitHub.</p>
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-dashed border-white/[0.08] p-12 text-center">
              <BookMarked className="h-10 w-10 text-gray-500 mx-auto mb-4" />
              <h3 className="text-base font-bold text-white font-sans">GitHub search failed</h3>
              <p className="text-xs text-gray-400 mt-1">Please try again in a moment.</p>
            </div>
          ) : filteredResults.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/[0.08] p-12 text-center">
              <BookMarked className="h-10 w-10 text-gray-500 mx-auto mb-4" />
              <h3 className="text-base font-bold text-white font-sans">No repositories found</h3>
              <p className="text-xs text-gray-400 mt-1">Try resetting your language filter or typing a simpler phrasing.</p>
              <button
                onClick={() => {
                  setSelectedLanguage('All');
                }}
                className="mt-4 px-4 py-2 rounded-xl bg-[#8B5CF6] text-xs font-semibold text-white"
              >
                Reset Filters
              </button>
            </div>
         ) : (
  filteredResults.map((repo, idx) => {
    // Defensive normalization: search results may come from different
    // API/result shapes, so never assume fields are defined.
    const safeFullName = String(
      repo.fullName ??
      (repo as any).full_name ??
      repo.name ??
      'unknown-repository'
    );

    const safeName = String(repo.name ?? '');
    const safeDescription = String(repo.description ?? '');
    const safeLanguage = String(repo.language ?? 'Unknown');

    const safeTopics = Array.isArray(repo.topics)
      ? repo.topics.map(topic => String(topic ?? '')).filter(Boolean)
      : [];

    const safeStars =
      typeof repo.stars === 'number' && Number.isFinite(repo.stars)
        ? repo.stars
        : 0;

    const safeForks =
      typeof repo.forks === 'number' && Number.isFinite(repo.forks)
        ? repo.forks
        : 0;

    const safeHtmlUrl = String(
      repo.html_url ??
      repo.url ??
      `https://github.com/${safeFullName}`
    );

    const repoUrl = safeHtmlUrl;
    const repoSlug = safeFullName.replace(/\//g, '-');

    const isAnalyzing = analyzingRepoUrl === repoUrl;
    const analyzeMessage = analyzeMessageByUrl[repoUrl];

    return (
      <div
        key={`${safeFullName}-${idx}`}
        id={`repo-card-${repoSlug}`}
        className="group relative rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/[0.01] p-6 transition-all duration-300"
      >
        {/* Horizontal Layout block */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2">

            {/* Repo Title and Indicator */}
            <div className="flex items-center gap-2">
              <BookMarked className="h-4.5 w-4.5 text-gray-400 group-hover:text-[#8B5CF6] transition-colors" />

              <h3
                className="text-lg font-bold text-white tracking-tight font-mono group-hover:underline cursor-pointer"
                onClick={() => apiAvailable && onAnalyze(repoUrl)}
              >
                {safeFullName}
              </h3>
            </div>

            {/* Repository Description */}
            <p className="text-sm text-gray-400 leading-relaxed max-w-2xl font-sans">
              {safeDescription || 'No description available.'}
            </p>

            <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
              <span className={`rounded-md border px-2 py-1 ${repo.evidence_readiness === 'ready' ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300' : repo.evidence_readiness === 'unknown' ? 'border-amber-500/20 bg-amber-500/5 text-amber-300' : 'border-white/10 bg-white/[0.03] text-gray-400'}`}>
                Analysis evidence: {repo.evidence_readiness || 'unknown'}
              </span>
              {typeof repo.relevance_score === 'number' && <span className="text-gray-500">Relevance {repo.relevance_score}</span>}
              {repo.tree_inspection_state && repo.tree_inspection_state !== 'inspected' && <span className="text-amber-400">Tree {repo.tree_inspection_state.replace('_', ' ')}</span>}
            </div>

            {/* Tag Topics List */}
            {safeTopics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {safeTopics.map((topic, topicIndex) => (
                  <span
                    key={`${topic}-${topicIndex}`}
                    className="text-[11px] font-mono text-purple-300/80 bg-[#8B5CF6]/5 px-2 py-0.5 rounded-md border border-[#8B5CF6]/10 animate-fade-in"
                  >
                    #{topic}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Action Analyze Right Bar */}
          <div className="flex sm:flex-col items-end justify-between sm:justify-start gap-4 shrink-0">
            <button
              onClick={() => onAnalyze(repoUrl)}
              disabled={!apiAvailable || isAnalyzing}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#8B5CF6] to-purple-700 hover:from-purple-500 hover:to-purple-600/90 text-xs font-semibold text-white tracking-wide shadow-md transition-transform cursor-pointer hover:translate-x-0.5 flex items-center gap-1.5 disabled:opacity-60 disabled:cursor-wait"
              id={`analyze-btn-${repoSlug}`}
            >
              {isAnalyzing ? 'Cloning...' : 'Analyze Repo'}
              <ChevronRight className="h-3.5 w-3.5" />
            </button>

            {analyzeMessage && (
              <span
                className={`text-[11px] font-mono ${
                  analyzeMessage === 'Repository cloned successfully'
                    ? 'text-emerald-400'
                    : 'text-red-400'
                }`}
              >
                {analyzeMessage}
              </span>
            )}

            {/* Quick Stats */}
            <div className="flex items-center gap-3 text-xs text-gray-400 font-mono">
              <div className="flex items-center gap-1 hover:text-white transition-colors">
                <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
                <span>{safeStars.toLocaleString()}</span>
              </div>

              <div className="flex items-center gap-1 hover:text-white transition-colors">
                <GitFork className="h-3.5 w-3.5 text-blue-400" />
                <span>{safeForks.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer specs inside card */}
        <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center justify-between text-xs text-gray-500 font-mono">
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                languageColors[safeLanguage] || 'bg-gray-500'
              }`}
            />
            <span>Language: {safeLanguage}</span>
          </div>

          <div className="truncate max-w-[50%]">
            {repoUrl}
          </div>
        </div>
      </div>
    );
  })
)}
        </div>
      </div>
    </div>
  );
}
