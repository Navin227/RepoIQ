import React, { useEffect, useState } from 'react';
import { RepositoryReadme } from './RepositoryReadme';
import {
  Star, GitFork, BookMarked, Terminal, Code,
  ChevronRight, Share2, ExternalLink, Sparkles,
  AlertCircle, ArrowRight, Clock, Cpu,
  Award, BookOpen, Folder, File, ChevronDown, HelpCircle
} from 'lucide-react';
import {
  ArchitectureComponent,
  ExecutiveOverview,
  FileTreeNode,
  Repository,
  TechItem,
  TechStack,
} from '../types';

interface AnalysisDashboardProps {
  repo: Repository;
  isSaved: boolean;
  onSaveToggle: (fullName: string) => void;
  onBackToSearch: () => void;
  onAnalyze: (repoUrl: string) => void;
  apiAvailable: boolean;
}

function getEvidenceText(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value : UNKNOWN_EVIDENCE;
}

function isFileTreeNode(value: unknown): value is FileTreeNode {
  return Boolean(
    value &&
    typeof value === 'object' &&
    'name' in value &&
    typeof value.name === 'string' &&
    value.name.trim().length > 0 &&
    'type' in value &&
    (value.type === 'file' || value.type === 'folder')
  );
}

function normalizeFileTree(value: unknown): FileTreeNode[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isFileTreeNode).map((node) => ({
    name: node.name,
    type: node.type,
    size: typeof node.size === 'string' ? node.size : undefined,
    children: normalizeFileTree(node.children),
  }));
}

const UNKNOWN_EVIDENCE = 'Unable to confidently determine from repository evidence.';

function getOptionalEvidenceText(value: unknown): string {
  if (typeof value !== 'string') return '';
  const text = value.trim();
  if (!text || /^(unknown|n\/a|not available|unable to confidently determine from repository evidence\.?|performs a specific runtime responsibility inferred from repository architecture evidence\.?)$/i.test(text)) return '';
  if (/unable to confidently determine from repository evidence/i.test(text)) return '';
  return text;
}

function getStringList(value: unknown): string[] {
  if (typeof value === 'string') return value.trim() ? [value] : [];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function isTechItem(value: unknown): value is TechItem {
  if (typeof value === 'string') return value.trim().length > 0;
  return Boolean(
    value &&
    typeof value === 'object' &&
    'name' in value &&
    typeof value.name === 'string' &&
    value.name.trim().length > 0
  );
}

function getTechItems(value: unknown): TechItem[] {
  return Array.isArray(value) ? value.filter(isTechItem) : [];
}

const TECH_STACK_CATEGORIES: Array<{ key: keyof TechStack; title: string }> = [
  { key: 'frontend', title: 'Frontend' },
  { key: 'backend', title: 'Backend' },
  { key: 'database', title: 'Database' },
  { key: 'infrastructure', title: 'Infrastructure' },
  { key: 'devops', title: 'DevOps' },
  { key: 'cloud', title: 'Cloud' },
  { key: 'messaging', title: 'Messaging' },
  { key: 'monitoring', title: 'Monitoring' },
  { key: 'cicd', title: 'CI/CD' },
  { key: 'tooling', title: 'Tooling' },
];

// Recursive Folder Tree Explorer Element
interface FolderTreeProps {
  node: FileTreeNode;
  depth: number;
}

function FolderTree({ node, depth }: FolderTreeProps) {
  const [isOpen, setIsOpen] = useState(depth === 0 || node.name === "src" || node.name === "packages");
  const children = Array.isArray(node.children) ? node.children : [];
  const hasChildren = node.type === 'folder' && children.length > 0;

  return (
    <div className="select-none font-mono text-xs">
      <button
        type="button"
        onClick={() => {
          if (hasChildren) setIsOpen(!isOpen);
        }}
        aria-expanded={node.type === 'folder' ? isOpen : undefined}
        disabled={!hasChildren}
        className={`flex items-center justify-between py-1.5 px-2 rounded-lg w-full text-left border-0 bg-transparent transition-colors ${hasChildren
            ? 'hover:bg-white/[0.03] text-purple-200'
            : 'text-gray-300 cursor-default'
          }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <div className="flex items-center gap-2 overflow-hidden">
          {node.type === 'folder' ? (
            <>
              <ChevronDown
                className={`h-3.5 w-3.5 text-gray-500 transition-transform duration-200 shrink-0 ${isOpen ? 'transform rotate-0' : 'transform -rotate-90'
                  }`}
              />
              <Folder className="h-4 w-4 text-indigo-400 shrink-0" />
            </>
          ) : (
            <>
              <span className="w-3.5 shrink-0" />
              <File className="h-4 w-4 text-gray-400 shrink-0" />
            </>
          )}
          <span className="truncate break-all">{node.name}</span>
        </div>

        {node.size && (
          <span className="text-[10px] text-gray-500 bg-white/[0.02] px-2 py-0.5 rounded border border-white/[0.04] shrink-0 font-mono">
            {node.size}
          </span>
        )}
      </button>

      {node.type === 'folder' && isOpen && children.length > 0 && (
        <div className="mt-0.5 border-l border-white/[0.04] ml-4.5 sm:ml-6">
          {children.map((child, idx) => (
            <FolderTree key={`${child.type}-${child.name}-${idx}`} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalysisDashboard({ repo, isSaved, onSaveToggle, onBackToSearch, onAnalyze, apiAvailable }: AnalysisDashboardProps) {
  const [viewMode, setViewMode] = useState<'overview' | 'analysis'>('overview');
  const [activeTab, setActiveTab] = useState<'architecture' | 'technology' | 'structure' | 'readme'>('architecture');

  useEffect(() => {
    console.info('[RepoIQ analysis]', {
      analysis_run_id: repo.analysisRunId || 'missing',
      event: 'frontend_result_rendered',
      repository: repo.fullName,
      commit_sha: repo.commitSha,
      final_state: repo.analysisStatus === 'running'
        ? 'in_progress'
        : repo.analysisStatus === 'error'
          ? 'failure'
          : repo.analysisStatus === 'partial' || repo.analysisStatus === 'degraded'
            ? repo.analysisStatus
            : 'success',
      module_count: repo.analysis.businessModules?.length || 0,
      feature_count: repo.analysis.keyFeatures.length,
    });
  }, [repo.fullName]);

  const headerDescription = getEvidenceText(repo.description);
  const architectureData = repo.architecture;
  const architecturePrimarySummary = getOptionalEvidenceText(architectureData?.architecture_summary);
  const architectureSummary = architecturePrimarySummary || getOptionalEvidenceText(architectureData?.summary);
  const architectureType = getOptionalEvidenceText(architectureData?.architecture_type);
  const architectureFlow = getStringList(architectureData?.flow).map(getOptionalEvidenceText).filter(Boolean);
  const requestLifecycle = getStringList(architectureData?.request_lifecycle).map(getOptionalEvidenceText).filter(Boolean);
  const supportedArchitectureComponents = (Array.isArray(architectureData?.components) ? architectureData.components : [])
    .filter((component) =>
      Boolean(component) &&
      typeof component.name === 'string' &&
      component.name.trim().length > 0 &&
      typeof component.responsibility === 'string' &&
      getOptionalEvidenceText(component.responsibility).length > 0 &&
      !['response', 'request', 'result', 'data', 'component', 'module', 'service', 'system'].includes(component.name.trim().toLowerCase())
    );
  const supportedArchitectureComponentNames = new Set(
    supportedArchitectureComponents.map((component) => component.name.trim().toLocaleLowerCase())
  );
  const componentCards: ArchitectureComponent[] = supportedArchitectureComponents
    .map((component) => ({
      name: component.name,
      responsibility: getOptionalEvidenceText(component.responsibility),
      connected_to: getStringList(component.connected_to).filter((value) =>
        getOptionalEvidenceText(value) && supportedArchitectureComponentNames.has(value.trim().toLocaleLowerCase())
      ),
      input: getOptionalEvidenceText(component.input),
      output: getOptionalEvidenceText(component.output),
      communicates_with: getStringList(component.communicates_with).filter((value) =>
        getOptionalEvidenceText(value) && supportedArchitectureComponentNames.has(value.trim().toLocaleLowerCase())
      ),
      connection_evidence_status: component.connection_evidence_status,
    }));
  const communicationPatterns = getStringList(architectureData?.communication)
    .map(getOptionalEvidenceText).filter(Boolean);
  const syncPath = getStringList(architectureData?.sync_path).map(getOptionalEvidenceText).filter(Boolean);
  const asyncPath = getStringList(architectureData?.async_path).map(getOptionalEvidenceText).filter(Boolean);
  const deploymentSummary = getOptionalEvidenceText(architectureData?.deployment);
  const rawExecutiveOverview = repo.overview?.executiveOverview;
  const genericNarrativePatterns = [
    /brings? the project files/i,
    /documented purpose/i,
    /visible repository structure/i,
    /usable product or tool/i,
    /available repository evidence/i,
    /main application experience/i,
    /supporting project areas/i,
    /operational setup/i,
    /primary purpose is inferred from the readme/i,
    /code organized into modules for application behavior/i,
  ];
  const cleanNarrative = (value: string) => {
    if (value === UNKNOWN_EVIDENCE) return value;
    return (value.match(/[^.!?]+[.!?]*/g) ?? [value])
      .map((sentence) => sentence.trim())
      .filter((sentence) => sentence && !genericNarrativePatterns.some((pattern) => pattern.test(sentence)))
      .join(' ')
      .trim();
  };
  const overviewSummary = cleanNarrative(getEvidenceText(repo.overview?.aiSummary));
  const repositoryDescription = getEvidenceText(repo.description);
  const genericFeatureNames = new Set([
    'backend', 'database', 'platform', 'www',
    'docs', 'documentation', 'tests', 'test', 'services', 'components',
    'controllers', 'models', 'utils', 'utilities', 'infrastructure',
  ]);
  const isRepositoryAreaFeature = (feature: { name: string; description: string }) => {
    const name = feature.name.trim().toLocaleLowerCase();
    const description = feature.description.trim().toLocaleLowerCase();
    return name.startsWith('.') || genericFeatureNames.has(name) || [
      /top-level repository module/,
      /user-facing interface and client-side application code/,
      /persistence layer for application data and metadata/,
      /area visible in repository structure/,
    ].some((pattern) => pattern.test(description));
  };
  const displayedFeatureNames = new Set<string>();
  const executiveOverview: ExecutiveOverview = {
    what_is_this_project: getStringList(rawExecutiveOverview?.what_is_this_project).length > 0
      ? getStringList(rawExecutiveOverview?.what_is_this_project)
          .map(cleanNarrative)
          .filter((item) => item && item !== UNKNOWN_EVIDENCE)
      : [overviewSummary !== UNKNOWN_EVIDENCE ? overviewSummary : repositoryDescription],
    why_was_it_built: cleanNarrative(getEvidenceText(rawExecutiveOverview?.why_was_it_built)),
    user_features: Array.isArray(rawExecutiveOverview?.user_features)
      ? rawExecutiveOverview.user_features.filter((feature) =>
          feature &&
          typeof feature.name === 'string' &&
          feature.name.trim().length > 0 &&
          typeof feature.description === 'string' &&
          feature.description.trim().length > 0 &&
          !isRepositoryAreaFeature(feature) &&
          !displayedFeatureNames.has(feature.name.trim().toLocaleLowerCase()) &&
          Boolean(displayedFeatureNames.add(feature.name.trim().toLocaleLowerCase()))
        )
      : [],
    typical_use_cases: getStringList(rawExecutiveOverview?.typical_use_cases)
      .map(cleanNarrative)
      .filter((item) => item && item !== UNKNOWN_EVIDENCE),
    end_user_use_cases: Array.isArray(rawExecutiveOverview?.end_user_use_cases)
      ? rawExecutiveOverview.end_user_use_cases
          .filter((item): item is { title: string; description: string; evidence?: string[] } =>
            Boolean(item) && typeof item.title === 'string' && typeof item.description === 'string')
          .map((item) => ({
            title: cleanNarrative(item.title),
            description: cleanNarrative(item.description),
            evidence: getStringList(item.evidence),
          }))
          .filter((item) => item.title && item.description && item.description !== UNKNOWN_EVIDENCE)
      : [],
    who_is_this_for: getStringList(rawExecutiveOverview?.who_is_this_for)
      .map(cleanNarrative)
      .filter((item) => item && item !== UNKNOWN_EVIDENCE),
    why_is_it_valuable: cleanNarrative(getEvidenceText(rawExecutiveOverview?.why_is_it_valuable)),
    one_line_summary: cleanNarrative(getEvidenceText(rawExecutiveOverview?.one_line_summary)) !== UNKNOWN_EVIDENCE
      ? cleanNarrative(getEvidenceText(rawExecutiveOverview?.one_line_summary))
      : overviewSummary,
  };
  const overviewDetails = [
    { title: 'Why it was built', value: getOptionalEvidenceText(executiveOverview.why_was_it_built) },
    { title: 'Who it serves', value: executiveOverview.who_is_this_for.map(getOptionalEvidenceText).filter(Boolean).join(', ') },
    { title: 'Why it is valuable', value: getOptionalEvidenceText(executiveOverview.why_is_it_valuable) },
  ].filter((detail) => detail.value);
  const overviewFeatures = executiveOverview.user_features
    .filter((feature) => getOptionalEvidenceText(feature.name) && getOptionalEvidenceText(feature.description));
  const folderStructure = normalizeFileTree(repo.folderStructure);
  const repositoryLanguages = getStringList(repo.languages);
  const languages = repositoryLanguages.length > 0
    ? repositoryLanguages
    : getStringList(repo.rawStack?.languages);
  const technologySections = TECH_STACK_CATEGORIES.map(({ key, title }) => {
    const rawItems = getTechItems(repo.rawStack?.categories?.[key]);
    const analysisItems = getTechItems(repo.analysis?.techStack?.[key]);
    return {
      title,
      items: rawItems.length > 0 ? rawItems : analysisItems,
    };
  });

  const developerTabs = [
    { id: 'architecture', label: 'Architecture & Flow' },
    { id: 'technology', label: 'Technology Stack' },
    { id: 'structure', label: 'Repository Structure' },
    { id: 'readme', label: 'README' }
  ] as const;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10" id="analysis-dashboard">

      {/* Breadcrumbs Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-white/[0.08] pb-6 mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-500 font-mono">
            <button onClick={onBackToSearch} className="hover:text-white transition-colors cursor-pointer bg-transparent border-0 p-0 text-left">RepoIQ</button>
            <ChevronRight className="h-3 w-3" />
            <span>Analysis</span>
            <ChevronRight className="h-3 w-3" />
            <span className="text-gray-300">{repo.fullName}</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              {repo.fullName}
            </h1>
            <a
              href={repo.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 text-xs text-purple-300 hover:text-white bg-purple-500/10 hover:bg-[#8B5CF6]/20 border border-[#8B5CF6]/20 rounded-lg px-2.5 py-1.5 transition-all"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span>GitHub Link</span>
            </a>
            {repo.analysisStatus !== 'partial' && <span className={`inline-flex items-center rounded-lg border px-2.5 py-1.5 text-xs font-medium ${['complete', 'ai_generated'].includes(repo.analysisStatus || '') ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200' : repo.analysisStatus === 'unavailable' || repo.analysisStatus === 'failed' ? 'border-red-400/20 bg-red-400/10 text-red-200' : 'border-amber-400/20 bg-amber-400/10 text-amber-200'}`}>
              {['complete', 'ai_generated'].includes(repo.analysisStatus || '') ? 'Evidence analysis complete' : `Analysis ${repo.analysisStatus || 'status unavailable'}`}
            </span>}
          </div>
          {headerDescription !== UNKNOWN_EVIDENCE && <p className="text-sm text-gray-400 mt-2 max-w-2xl font-sans leading-relaxed">{headerDescription}</p>}
        </div>

        {/* Saved Favorites & Share layout buttons */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => onAnalyze(repo.url)}
            disabled={!apiAvailable}
            title={apiAvailable ? 'Re-analyze repository' : 'API endpoint is not configured'}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 bg-white/[0.03] text-gray-300 border border-white/[0.06] hover:bg-white/[0.06]"
          >
            <Sparkles className="h-4 w-4 text-purple-300" />
            <span>Re-analyze</span>
          </button>
          <button
            onClick={() => onSaveToggle(repo.fullName)}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer ${isSaved
                ? 'bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.3)]'
                : 'bg-white/[0.03] text-gray-300 border border-white/[0.06] hover:bg-white/[0.06]'
              }`}
          >
            <Star className={`h-4.5 w-4.5 ${isSaved ? 'fill-white text-white' : 'text-gray-400'}`} />
            <span>{isSaved ? 'Saved in Library' : 'Save Repository'}</span>
          </button>

          <button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(window.location.href);
                alert("Copied repository link to clipboard!");
              } catch (error) {
                console.error('Could not copy repository link:', error);
                alert("Unable to copy the repository link. Please copy it from the address bar.");
              }
            }}
            className="p-2.5 rounded-xl bg-white/[0.03] text-gray-400 hover:text-white border border-white/[0.06] hover:bg-white/[0.06] transition-all cursor-pointer"
            title="Share Analysis"
          >
            <Share2 className="h-4.5 w-4.5" />
          </button>
        </div>
      </div>

      {(repo.analysisStatus === 'running' || repo.analysisStatus === 'error') && (
        <div
          role={repo.analysisStatus === 'error' ? 'alert' : 'status'}
          className={`mb-6 rounded-xl border px-4 py-3 text-sm ${repo.analysisStatus === 'error'
            ? 'border-red-400/20 bg-red-500/10 text-red-200'
            : 'border-purple-400/20 bg-purple-500/10 text-purple-200'
          }`}
        >
          <p className="font-semibold">
            {repo.analysisStatus === 'running' ? 'Analysis in progress' : 'Analysis could not be completed'}
          </p>
          <p className="mt-1 text-current/80">
            {repo.analysisStatus === 'running'
              ? 'Connecting to the configured analysis API and retrieving repository evidence.'
              : repo.analysisError || 'The configured analysis API did not return a result.'}
          </p>
          {repo.analysisRunId && (
            <p className="mt-1 font-mono text-xs opacity-75">Correlation ID: {repo.analysisRunId}</p>
          )}
        </div>
      )}

      {/* Mode Perspective Selector */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 mb-8 bg-white/[0.01] border border-white/[0.05] p-3 rounded-2xl">
        <div className="flex flex-col sm:flex-row bg-black/40 border border-white/[0.08] p-1 rounded-xl w-full lg:w-auto gap-1">
          <button
            onClick={() => setViewMode('overview')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'overview'
                ? 'bg-gradient-to-r from-purple-500/20 to-purple-600/10 text-purple-300 border border-purple-500/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <HelpCircle className="h-4 w-4" />
            <span>📊 Executive Overview</span>
          </button>

          <button
            onClick={() => setViewMode('analysis')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'analysis'
                ? 'bg-gradient-to-r from-[#8B5CF6]/20 to-purple-600/10 text-white border border-[#8B5CF6]/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <Terminal className="h-4 w-4" />
            <span>💻 Technical Deep-Dive</span>
          </button>
        </div>
      </div>

      {/* -----------------perspective 1: EXECUTIVE OVERVIEW -----------------*/}
      {viewMode === 'overview' && (
        <div className="space-y-8 animate-fade-in" id="executive-overview-frame">
          <div className="rounded-2xl bg-gradient-to-br from-[#8B5CF6]/10 to-transparent border border-[#8B5CF6]/15 p-6 sm:p-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 h-48 w-48 bg-[#8B5CF6]/10 blur-[80px] rounded-full pointer-events-none" />
            <div className="relative">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#8B5CF6] uppercase tracking-wider mb-3">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Executive Overview</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight font-sans">
                What is this Project?
              </h3>
              <div className="mt-4 space-y-4">
                {executiveOverview.what_is_this_project.slice(0, 3).map((paragraph, idx) => (
                  <p key={idx} className="text-gray-200 text-sm sm:text-base leading-relaxed font-sans">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>
          </div>

          {(overviewDetails.length > 0 || overviewFeatures.length > 0) && <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {overviewDetails.length > 0 && <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Project Context</h4>
              <div className="space-y-4">
                {overviewDetails.map((detail) => <div key={detail.title}>
                  <h5 className="text-sm font-semibold text-white">{detail.title}</h5>
                  <p className="mt-1 text-sm leading-relaxed text-gray-400">{detail.value}</p>
                </div>)}
              </div>
            </div>}
            {overviewFeatures.length > 0 && <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Verified Capabilities</h4>
              <div className="space-y-4">
                {overviewFeatures.slice(0, 8).map((feature) => <div key={feature.name}>
                  <h5 className="text-sm font-semibold text-white">{feature.name}</h5>
                  <p className="mt-1 text-sm leading-relaxed text-gray-400">{feature.description}</p>
                </div>)}
              </div>
            </div>}
          </div>}

        </div>
      )}

      {/* -----------------perspective 2: DEVELOPER ADVANCED ANALYSIS HUB -----------------*/}
      {viewMode === 'analysis' && (
        <div className="space-y-8 animate-fade-in" id="developer-analysis-frame">

          {/* Sub-navigation tabs inside Developer Hub */}
          <div className="border-b border-white/[0.08] mb-6">
            <div className="flex space-x-1 sm:space-x-4 overflow-x-auto pb-px scrollbar-none">
              {developerTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer shrink-0 whitespace-nowrap ${activeTab === tab.id
                      ? 'text-white bg-white/[0.05] border border-white/[0.08] shadow-sm'
                      : 'text-gray-400 hover:text-white hover:bg-white/[0.01]'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Rendering the Active developer sub-tab */}
          <div className="mt-4">

            {/* SUB-TAB 1: ARCHITECTURE & REQUEST FLOW */}
            {activeTab === 'architecture' && (
              <div className="space-y-8" id="dev-tab-architecture">

                {/* Visual Architecture Diagram card */}
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-6 sm:p-8">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <span className="text-xs font-mono text-gray-500 uppercase tracking-widest block">Architecture Summary</span>
                      {architectureSummary && <p className="text-sm text-gray-300 leading-relaxed">{architectureSummary}</p>}
                    </div>
                    {architectureType && <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-3 w-full max-w-xs">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-[#c4b5fd]">Inferred Type</div>
                      <div className="mt-1 text-sm font-semibold text-white">{architectureType}</div>
                    </div>}
                  </div>

                <div className="mt-8 pt-4 border-t border-white/[0.06]">
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Architecture Components</h4>
                  {componentCards.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {componentCards.map((component, index) => (
                        <div key={component.name + index} className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                          <div className="flex items-center gap-2 mb-3">
                            <div className="h-7 w-7 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
                              <Code className="h-4 w-4 text-purple-400" />
                            </div>
                            <span className="text-xs font-bold text-white">{component.name}</span>
                          </div>
                          {component.responsibility && <p className="text-xs text-gray-300 leading-relaxed">{component.responsibility}</p>}
                          {component.connected_to.length > 0 && <div className="mt-4 pt-3 border-t border-white/[0.04]">
                            <span className="text-[9px] font-mono uppercase tracking-wider text-gray-500">Connected Components</span>
                            <p className="mt-1 text-[11px] text-gray-400 break-words">
                              {component.connected_to.join(', ')}
                            </p>
                          </div>}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
                </div>

                {/* Structured Request Flow Walkthrough */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Incremental Request Flow</h4>
                  <div className="rounded-2xl bg-white/[0.01] border border-white/[0.05] p-5 sm:p-6 space-y-4 relative">
                    <div className="absolute left-8 top-10 bottom-10 w-px bg-[#8B5CF6]/20 hidden sm:block" />
                    {architectureFlow.length > 0 ? architectureFlow.map((step, i) => (
                      <div key={`${step}-${i}`} className="flex gap-4 items-center relative z-10">
                        <span className="h-6.5 w-6.5 rounded-full bg-purple-950 border border-[#8B5CF6]/40 text-[#8B5CF6] flex items-center justify-center text-xs font-mono shrink-0 font-bold">
                          {i + 1}
                        </span>
                        <div className="flex-1 bg-black/40 border border-white/[0.04] rounded-xl p-3.5 hover:bg-white/[0.02] hover:border-white/[0.08] transition-all">
                          <span className="font-bold text-xs text-[#8B5CF6] uppercase tracking-wider font-mono">{step}</span>
                        </div>
                      </div>
                    )) : null}
                    <div className="pt-4 border-t border-white/[0.05] space-y-3">
                      <h5 className="text-[10px] font-mono uppercase tracking-widest text-gray-500">Request Lifecycle</h5>
                      {requestLifecycle.length > 0 ? requestLifecycle.map((lifecycleStep, index) => (
                        <div key={`${lifecycleStep}-${index}`} className="rounded-xl border border-white/[0.04] bg-black/30 px-4 py-3 text-xs text-gray-300">
                          {lifecycleStep}
                        </div>
                      )) : (
                        <p className="text-sm text-gray-400">No lifecycle details were supported by inspected repository evidence.</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Synchronous Path</h4>
                    <div className="space-y-3 text-sm text-gray-300">
                      {syncPath.length > 0 ? syncPath.map((step, index) => (
                        <div key={`${step}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3">
                          {step}
                        </div>
                      )) : <p>No synchronous path was supported by inspected repository evidence.</p>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Asynchronous Path</h4>
                    <div className="space-y-3 text-sm text-gray-300">
                      {asyncPath.length > 0 ? asyncPath.map((step, index) => (
                        <div key={`${step}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3">
                          {step}
                        </div>
                      )) : <p>No asynchronous path was supported by inspected repository evidence.</p>}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Communication Patterns</h4>
                    <div className="space-y-3">
                      {communicationPatterns.length > 0 ? communicationPatterns.map((item, index) => (
                        <div key={`${item}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3 text-sm text-gray-300">
                          {item}
                        </div>
                      )) : (
                        <p className="text-sm text-gray-400">No communication patterns were supported by inspected repository evidence.</p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Deployment Overview</h4>
                    <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-4 text-sm text-gray-200">
                      {deploymentSummary || 'No deployment details were supported by inspected repository evidence.'}
                    </div>
                  </div>
                </div>

              </div>
            )}

            {activeTab === 'readme' && (
              <RepositoryReadme repo={repo} />
            )}

            {/* SUB-TAB 2: TECHNOLOGY STACK */}
            {activeTab === 'technology' && (
              <div className="space-y-8" id="dev-tab-technology">
                {/* LANGUAGES SECTION */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Detected Languages</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                    {languages.length > 0 ? (
                      languages.map((lang, idx) => (
                        <div key={idx} className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-3 py-2">
                          <div className="font-medium text-gray-200 text-sm">{lang}</div>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-gray-400 col-span-full">No languages detected yet.</p>
                    )}
                  </div>
                </div>

                {/* TECHNOLOGIES SECTION */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Detected Technology Stack</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {technologySections.map((section) => (
                        <div key={section.title} className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6">
                          <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-3">{section.title}</h5>
                          {section.items.length > 0 ? (
                            <div className="space-y-3">
                              {section.items.map((item, idx) => {
                                const name = getTechName(item);
                                if (typeof item === 'string') {
                                  return (
                                    <div key={`${name}-${idx}`} className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-4 py-3">
                                      <div className="font-medium text-gray-200">{name}</div>
                                    </div>
                                  );
                                }

                                const sourceFiles = getStringList(item.sources);
                                const source = typeof item.source === 'string' && item.source.trim()
                                  ? item.source
                                  : undefined;
                                const evidence = getStringList(item.evidence);
                                const evidenceCount = typeof item.count === 'number' && Number.isFinite(item.count) && item.count >= 0
                                  ? item.count
                                  : sourceFiles.length > 0
                                    ? sourceFiles.length
                                    : undefined;

                                return (
                                  <div key={`${name}-${idx}`} className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-4 py-3">
                                    <div className="font-medium text-gray-200">{name}</div>
                                    {evidenceCount !== undefined && (
                                      <div className="text-xs text-gray-400 mt-1.5">
                                        Found in {evidenceCount} {evidenceCount === 1 ? 'file' : 'files'}
                                      </div>
                                    )}
                                    {(sourceFiles.length > 0 || source || evidence.length > 0) && (
                                      <details className="mt-3 text-xs text-gray-400">
                                        <summary className="cursor-pointer text-gray-300">Evidence</summary>
                                        {sourceFiles.length > 0 && (
                                          <ul className="mt-2 space-y-1 max-h-40 overflow-auto pr-1">
                                            {sourceFiles.map((sourceFile, sourceIdx) => (
                                              <li key={`${sourceFile}-${sourceIdx}`} className="font-mono text-[11px] text-gray-400 break-all">
                                                {sourceFile}
                                              </li>
                                            ))}
                                          </ul>
                                        )}
                                        {source && (
                                          <p className="mt-2 font-mono text-[11px] text-gray-400 break-all">{source}</p>
                                        )}
                                        {evidence.length > 0 && (
                                          <ul className="mt-2 space-y-1 max-h-40 overflow-auto pr-1">
                                            {evidence.map((itemEvidence, evidenceIdx) => (
                                              <li key={`${itemEvidence}-${evidenceIdx}`} className="text-[11px] text-gray-400 break-words">
                                                {itemEvidence}
                                              </li>
                                            ))}
                                          </ul>
                                        )}
                                      </details>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-400">No detected {section.title.toLowerCase()} technologies.</p>
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-TAB 3: REPOSITORY STRUCTURE */}
            {activeTab === 'structure' && (
              <div className="space-y-8" id="dev-tab-structure">
                <div>
                  <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <div>
                      <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest">Repository Structure</h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">Browse the cloned repository tree. Expand folders to inspect actual files and directories.</p>
                    </div>
                    <span className="text-[11px] font-mono text-gray-500 bg-black/40 px-3 py-1 rounded-lg border border-white/[0.05]">
                      Root: / {folderStructure.length > 0 ? folderStructure[0].children?.length ?? 0 : 0} top entries
                    </span>
                  </div>

                  <div className="rounded-2xl border border-white/[0.08] bg-black/50 p-4 sm:p-6 outline-none font-sans">
                    {folderStructure.length > 0 ? (
                      folderStructure.map((node, index) => (
                        <FolderTree key={`${node.type}-${node.name}-${index}`} node={node} depth={0} />
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01] p-6 text-center text-sm text-gray-400">
                        No repository structure available yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}


          </div>

        </div>
      )}

    </div>
  );
}
