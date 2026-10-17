import { useState } from 'react';
import { GitBranch, User, Menu, X, ArrowRight, Github, Sparkles, BookMarked, Layers, Square, Loader2 } from 'lucide-react';

interface DemoStatusResponse {
  state?: 'running' | 'pending' | 'stopping' | 'stopped' | 'shutting-down' | 'terminated' | string;
  status?: 'running' | 'pending' | 'stopping' | 'offline' | 'terminating' | 'terminated' | 'shutting-down' | string;
  public_ip: string | null;
  private_ip?: string | null;
  launch_time?: string | null;
  application_url?: string | null;
  instance_id: string | null;
  health?: 'offline' | 'ok' | 'initializing' | 'stopping' | string;
}

interface NavbarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  onNavigateHome: () => void;
  savedCount: number;
  adminToken?: string;
  demoStatus?: DemoStatusResponse | null;
  isDemoLoading?: boolean;
  onDemoStop?: () => void;
}

export default function Navbar({ 
  currentTab, 
  setCurrentTab, 
  onNavigateHome, 
  savedCount,
  adminToken = '',
  demoStatus = null,
  isDemoLoading = false,
  onDemoStop
}: NavbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { id: 'home', label: 'Home' },
    { id: 'explore', label: 'Explore' },
    { id: 'analyze', label: 'Analyze' },
    { id: 'saved', label: 'Saved', count: savedCount },
    { id: 'history', label: 'History' }
  ];

  // Determine if demo is currently running
  const demoState = demoStatus?.state || demoStatus?.status || 'offline';
  const isDemoRunning = demoState === 'running' && adminToken;

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-white/[0.08] bg-[#0B0B0F]/80 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          
          {/* Logo on Left */}
          <div 
            onClick={onNavigateHome}
            className="flex cursor-pointer items-center space-x-2.5 group"
            id="navbar-logo"
          >
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] shadow-[0_0_15px_rgba(139,92,246,0.25)] transition-transform duration-300 group-hover:scale-105">
              <GitBranch className="h-5 w-5 text-white" />
              <div className="absolute inset-0 rounded-xl bg-[#8B5CF6] opacity-0 blur-md transition-opacity duration-300 group-hover:opacity-60" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white font-sans">
              Repo<span className="bg-gradient-to-r from-[#8B5CF6] to-pink-500 bg-clip-text text-transparent">IQ</span>
            </span>
          </div>

          {/* Desktop Navigation Links (Middle) */}
          <div className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                id={`nav-link-${item.id}`}
                onClick={() => {
                  setCurrentTab(item.id);
                  if (item.id === 'home') onNavigateHome();
                }}
                className={`relative px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                  currentTab === item.id 
                    ? 'text-white bg-white/[0.04]' 
                    : 'text-gray-400 hover:text-white hover:bg-white/[0.02]'
                }`}
              >
                <span className="relative z-10 flex items-center gap-1.5">
                  {item.label}
                  {item.count !== undefined && item.count > 0 && (
                    <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[#8B5CF6] px-1 text-[10px] font-bold text-white">
                      {item.count}
                    </span>
                  )}
                </span>
                {currentTab === item.id && (
                  <div className="absolute bottom-[-17px] left-0 right-0 h-[2px] bg-gradient-to-r from-[#8B5CF6] to-pink-500 rounded-full" />
                )}
              </button>
            ))}
            <a 
              href="https://github.com" 
              target="_blank" 
              rel="noopener noreferrer"
              className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <Github className="h-4 w-4" />
              Github
            </a>
          </div>

          <div className="hidden md:flex items-center space-x-3">
            {isDemoRunning && onDemoStop && (
              <button
                onClick={onDemoStop}
                disabled={isDemoLoading}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-red-600/80 hover:bg-red-600 text-xs font-semibold text-white transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                title="Stop the running demo server"
              >
                {isDemoLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Square className="h-3.5 w-3.5 fill-white" />
                )}
                Stop Demo
              </button>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center rounded-md p-2 text-gray-400 hover:bg-white/[0.05] hover:text-white focus:outline-none"
              id="navbar-mobile-toggle"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-white/[0.08] bg-[#0B0B0F] py-3 px-4 space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setCurrentTab(item.id);
                if (item.id === 'home') onNavigateHome();
                setMobileMenuOpen(false);
              }}
              className={`w-full text-left px-4 py-2.5 rounded-lg text-base font-medium transition-colors ${
                currentTab === item.id 
                  ? 'text-white bg-[#8B5CF6]/15 border-l-2 border-[#8B5CF6]' 
                  : 'text-gray-400 hover:text-white hover:bg-white/[0.04]'
              }`}
            >
              <div className="flex items-center justify-between">
                <span>{item.label}</span>
                {item.count !== undefined && item.count > 0 && (
                  <span className="rounded-full bg-[#8B5CF6] px-2 py-0.5 text-xs font-bold text-white">
                    {item.count}
                  </span>
                )}
              </div>
            </button>
          ))}

        </div>
      )}
    </nav>
  );
}
