import React from 'react';
import { Play, Square, Key, Clock, ExternalLink, Server, Loader2, Wifi, CheckCircle2, ShieldAlert } from 'lucide-react';

interface DemoStatusResponse {
  state?: 'running' | 'pending' | 'stopping' | 'stopped' | 'shutting-down' | 'terminated' | string;
  status?: 'running' | 'pending' | 'stopping' | 'offline' | 'terminating' | 'terminated' | 'shutting-down' | string;
  public_ip: string | null;
  private_ip?: string | null;
  launch_time?: string | null;
  application_url?: string | null;
  instance_id: string | null;
  health?: 'offline' | 'ok' | 'initializing' | 'stopping' | 'unavailable' | string;
  message?: string;
}

interface DemoInfrastructureCardProps {
  serverStatus: 'checking' | 'starting' | 'online' | 'offline' | 'failed';
  adminToken: string;
  duration: 30 | 45 | 60;
  onDurationChange: (duration: 30 | 45 | 60) => void;
  demoStatus: DemoStatusResponse | null;
  demoSessionId: string | null;
  demoSessionEndTime: string | null;
  isDemoLoading: boolean;
  demoErrorMsg: string | null;
  demoSuccessMsg: string | null;
  demoRemainingTime: string;
  onTokenChange: (token: string) => void;
  onStart: () => void;
  onStop: () => void;
}

export default function DemoInfrastructureCard({
  serverStatus,
  adminToken,
  duration,
  onDurationChange,
  demoStatus,
  demoSessionId,
  demoSessionEndTime,
  isDemoLoading,
  demoErrorMsg,
  demoSuccessMsg,
  demoRemainingTime,
  onTokenChange,
  onStart,
  onStop
}: DemoInfrastructureCardProps) {
  // Compute derived state values
  const reportedState = demoStatus?.state || demoStatus?.status || 'offline';
  const currentState =
    serverStatus === 'online'
      ? 'running'
      : serverStatus === 'failed'
        ? 'failed'
        : serverStatus === 'starting' || serverStatus === 'checking'
          ? 'pending'
          : reportedState;
  const isPending = currentState === 'pending';
  const isRunning = currentState === 'running';
  const isStopping = currentState === 'stopping' || currentState === 'terminating' || currentState === 'shutting-down';
  const isOffline = !currentState || currentState === 'stopped' || currentState === 'offline' || currentState === 'terminated';
  const isFailed = currentState === 'failed';

  // Render status badge helpers
  const getStatusColor = () => {
    const state = currentState;
    switch (state) {
      case 'running':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'pending':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'failed':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'stopping':
      case 'terminating':
      case 'shutting-down':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'stopped':
      case 'offline':
      case 'terminated':
      default:
        return 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
    }
  };

  const getStatusText = () => {
    const state = currentState;
    switch (state) {
      case 'running':
        return 'Running';
      case 'pending':
        return 'Pending';
      case 'failed':
        return 'Failed';
      case 'stopping':
      case 'terminating':
      case 'shutting-down':
        return 'Terminating';
      case 'stopped':
      case 'offline':
      case 'terminated':
      default:
        return 'Offline';
    }
  };

  // Handler wrappers
  const handleTokenChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onTokenChange(e.target.value);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-8" id="demo-control-card">
      <div className="relative rounded-3xl bg-white/[0.02] border border-white/[0.08] backdrop-blur-xl p-8 overflow-hidden shadow-[0_0_50px_rgba(139,92,246,0.05)] transition-all duration-300">
        
        {/* Glow Effects */}
        <div className="absolute top-0 right-0 -z-10 h-32 w-32 rounded-full bg-[#8B5CF6]/10 blur-[50px]" />
        <div className="absolute bottom-0 left-0 -z-10 h-32 w-32 rounded-full bg-pink-500/5 blur-[50px]" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/[0.08] pb-6 mb-6">
          <div>
            <h2 className="text-xl font-extrabold text-white flex items-center gap-2 font-sans">
              <Server className="h-5 w-5 text-[#8B5CF6]" />
              Demo Infrastructure Control
            </h2>
            <p className="text-xs text-gray-400 mt-1 font-sans">
              Deploy and manage the RepoIQ demo cluster on demand.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400 font-mono">Status:</span>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor()} font-sans`}>
              {isPending && <Loader2 className="h-3 w-3 animate-spin" />}
              {isRunning && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />}
              {isStopping && <Loader2 className="h-3 w-3 animate-spin" />}
              {isFailed && <ShieldAlert className="h-3 w-3" />}
              {getStatusText()}
            </span>
          </div>
        </div>

        {/* Input Fields Container */}
        <div className="space-y-6">
          
          {/* Access Token Input */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2 font-mono flex items-center gap-1.5">
              <Key className="h-3.5 w-3.5 text-[#8B5CF6]" />
              Admin Access Token
            </label>
            <input
              type="password"
              value={adminToken}
              onChange={handleTokenChange}
              placeholder="Paste security token to authenticate..."
              className="w-full bg-white/[0.03] text-white placeholder-gray-600 border border-white/[0.08] focus:border-[#8B5CF6]/50 focus:ring-1 focus:ring-[#8B5CF6]/30 rounded-xl px-4 py-3 text-sm outline-none transition-all font-mono"
            />
            <p className="text-[10px] text-gray-500 mt-1.5 font-sans leading-relaxed">
              Token is kept only in component memory and is never persisted to storage.
            </p>
          </div>

          {/* Configuration when Offline */}
          {isOffline && (
            <div>
              <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2 font-mono flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-[#8B5CF6]" />
                Session Duration
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[30, 45, 60].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => onDurationChange(t as any)}
                    disabled={!adminToken}
                    className={`py-3 rounded-xl border text-sm font-semibold transition-all font-sans cursor-pointer ${
                      duration === t
                        ? 'bg-[#8B5CF6]/20 border-[#8B5CF6] text-white'
                        : 'bg-white/[0.02] border-white/[0.08] text-gray-400 hover:border-white/20'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {t} Minutes
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Pending Messages */}
          {isPending && (
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10 space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-amber-300 font-sans">
                <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
                Starting Infrastructure...
              </div>
              <ul className="text-[11px] text-gray-400 space-y-1 pl-6 list-disc font-sans leading-relaxed">
                <li>Waiting for EC2 instance to initialize...</li>
                <li>Bootstrapping Kubernetes environment...</li>
                <li>Ready link will appear below shortly.</li>
              </ul>
            </div>
          )}

          {/* Running State Info */}
          {isRunning && (
            <div className="p-5 rounded-2xl bg-emerald-500/[0.02] border border-emerald-500/10 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="block text-[10px] text-gray-400 uppercase tracking-wider font-mono">
                    Time Remaining
                  </span>
                  <span className="text-2xl font-bold text-white font-mono tracking-tight block mt-1">
                    {demoRemainingTime}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] text-gray-400 uppercase tracking-wider font-mono">
                    Session End Time
                  </span>
                  <span className="text-sm font-medium text-gray-300 font-mono block mt-2">
                    {demoSessionEndTime ? new Date(demoSessionEndTime).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>
              </div>

              {demoStatus?.public_ip && (
                <div className="pt-3 border-t border-white/[0.04] flex items-center justify-between gap-4">
                  <div>
                    <span className="block text-[10px] text-gray-400 uppercase tracking-wider font-mono">
                      Public IP Address
                    </span>
                    <span className="text-xs text-gray-300 font-mono block mt-1">
                      {demoStatus.public_ip}
                    </span>
                  </div>

                  {demoStatus.application_url && (
                    <a
                      href={demoStatus.application_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-xs font-bold text-white shadow-lg transition-all duration-200 cursor-pointer"
                    >
                      Open RepoIQ
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Stopping State Info */}
          {isStopping && (
            <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/10">
              <div className="flex items-center gap-2 text-xs font-medium text-red-300 font-sans">
                <Loader2 className="h-4 w-4 animate-spin text-red-400" />
                Stopping Infrastructure... Clean up in progress.
              </div>
            </div>
          )}

          {/* Action Messages */}
          {demoErrorMsg && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 font-sans">
              <ShieldAlert className="h-4.5 w-4.5 text-red-400 shrink-0 mt-0.5" />
              <span>{demoErrorMsg}</span>
            </div>
          )}

          {demoSuccessMsg && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 font-sans">
              <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400 shrink-0 mt-0.5" />
              <span>{demoSuccessMsg}</span>
            </div>
          )}

          {/* Primary Buttons */}
          <div className="flex gap-4 pt-2">
            {!isRunning && !isStopping && (
              <button
                type="button"
                onClick={onStart}
                disabled={!adminToken || isPending || isDemoLoading}
                className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl bg-gradient-to-r from-[#8B5CF6] to-purple-700 hover:from-purple-500 hover:to-purple-600 font-bold text-white shadow-lg shadow-[#8B5CF6]/10 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 cursor-pointer text-sm"
              >
                {isDemoLoading ? (
                  <Loader2 className="h-4.5 w-4.5 animate-spin" />
                ) : (
                  <Play className="h-4.5 w-4.5 fill-white" />
                )}
                Start Demo Server
              </button>
            )}

            {(isRunning || isPending || isStopping) && (
              <button
                type="button"
                onClick={onStop}
                disabled={!adminToken || isStopping || isDemoLoading}
                className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl bg-red-600 hover:bg-red-700 font-bold text-white shadow-lg shadow-red-600/10 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 cursor-pointer text-sm"
              >
                {isDemoLoading ? (
                  <Loader2 className="h-4.5 w-4.5 animate-spin" />
                ) : (
                  <Square className="h-4.5 w-4.5 fill-white" />
                )}
                Stop Demo Server
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
