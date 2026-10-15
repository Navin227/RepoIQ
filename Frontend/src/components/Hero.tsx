import React, { useState } from 'react';
import { Search, Sparkles, AlertCircle, ArrowRight, CornerDownLeft, Command } from 'lucide-react';

interface HeroProps {
  onSearch: (query: string) => void;
  apiAvailable: boolean;
}

export default function Hero({
  onSearch,
  apiAvailable,
}: HeroProps) {
  const [query, setQuery] = useState('');

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && apiAvailable) {
      onSearch(query);
    }
  };

  const handleSuggestionClick = (text: string) => {
    if (!apiAvailable) return;
    setQuery(text);
    onSearch(text);
  };

  const popularTags = [
    { label: 'File Sharing', value: 'File Sharing' },
    { label: 'AI SaaS', value: 'ai chatbot' },
    { label: 'DevOps', value: 'DevOps' },
    { label: 'Kubernetes', value: 'kubernetes dashboard' },
    { label: 'E-commerce', value: 'E-commerce' },
    { label: 'Developer Tools', value: 'Developer Tools' }
  ];

  const examples = [
    'file sharing platform',
    'ai chatbot',
    'kubernetes dashboard',
    'https://github.com/vercel/next.js'
  ];

  return (
    <div className="relative overflow-hidden py-24 sm:py-32" id="hero-section">
      {/* Background ambient glowing shapes */}
      <div className="absolute top-1/4 left-1/2 -z-10 h-[380px] w-[600px] -translate-x-1/2 rounded-full bg-gradient-to-r from-[#8B5CF6]/20 to-pink-500/10 blur-[130px]" />
      <div className="absolute top-10 left-12 -z-10 h-[180px] w-[180px] rounded-full bg-purple-600/5 blur-[80px]" />
      
      {/* Container constraint */}
      <div className="mx-auto max-w-5xl px-6 text-center lg:px-8">
        
        {/* Superior Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.08] mb-8 animate-fade-in">
          <Sparkles className="h-3.5 w-3.5 text-[#8B5CF6]" />
          <span className="text-xs text-purple-200/90 font-medium font-mono">
            V2.0 Core: Real-time Repository Analytics Engine Powered by AI
          </span>
        </div>

        {/* Hero Headings */}
        <h1 className="text-5xl font-extrabold tracking-tight text-white sm:text-7xl font-sans" id="hero-title">
          Understand Any <br />
          <span className="bg-gradient-to-r from-[#8B5CF6] via-purple-400 to-pink-500 bg-clip-text text-transparent">
            GitHub Repository
          </span>
        </h1>
        
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-gray-400 font-sans">
          Search repositories by idea, analyze codebases, detect tech stacks, and get AI-powered insights in seconds.
        </p>

        {/* Intelligent Search Area Container */}
        <div className="mt-10 max-w-3xl mx-auto">
          <form 
            onSubmit={handleFormSubmit}
            className="relative flex items-center p-2 rounded-2xl bg-white/[0.03] backdrop-blur-md border border-white/[0.08] focus-within:border-[#8B5CF6]/50 focus-within:ring-1 focus-within:ring-[#8B5CF6]/30 shadow-[0_0_30px_rgba(0,0,0,0.5)] transition-all duration-300"
            id="search-form"
          >
            <div className="flex-1 flex items-center pl-3">
              <Search className="h-5 w-5 text-gray-500 mr-3 shrink-0" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search project ideas or paste a GitHub repository URL..."
                className="w-full bg-transparent text-white placeholder-gray-500 py-3 text-base font-sans outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
                id="search-input"
              />
            </div>
            
            {/* Quick Command Info (Desktop Only) */}
            <div className="hidden sm:flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.05] text-xs text-gray-500 mr-2 font-mono">
              <Command className="h-3 w-3" />
              <span>Enter</span>
            </div>

            <button
              type="submit"
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl bg-gradient-to-r from-[#8B5CF6] to-purple-700 hover:from-purple-500 hover:to-purple-600 font-semibold text-white shadow-lg transition-all duration-200 cursor-pointer text-sm shrink-0 hover:translate-x-0.5 disabled:opacity-40 disabled:cursor-not-allowed"
              id="search-submit-btn"
              disabled={!apiAvailable}
            >
              Analyze Project
              <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </form>

          {/* Static Actionable Examples */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-2 gap-y-1.5 text-xs text-gray-500">
            <span className="font-mono">Try searching:</span>
            {examples.map((item, index) => (
              <button
                key={index}
                type="button"
                onClick={() => handleSuggestionClick(item)}
                className="px-2.5 py-1 rounded-md bg-white/[0.02] hover:bg-white/[0.06] text-gray-400 hover:text-white border border-white/[0.04] hover:border-white/[0.1] font-mono transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                disabled={!apiAvailable}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {/* Popular Tags List */}
        <div className="mt-12">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 font-mono">
            Popular Categories
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2.5">
            {popularTags.map((tag, index) => (
              <button
                key={index}
                onClick={() => handleSuggestionClick(tag.value)}
                className="px-4 py-2 rounded-xl bg-white/[0.03] text-sm text-gray-300 border border-white/[0.06] hover:border-[#8B5CF6]/50 hover:bg-[#8B5CF6]/5 transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                disabled={!apiAvailable}
              >
                {tag.label}
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
