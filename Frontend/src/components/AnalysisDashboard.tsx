import React, { useEffect, useState } from 'react';
import { RepositoryReadme } from './RepositoryReadme';
import {
  Star, GitFork, BookMarked, Terminal, Code, Database, Globe,
  Settings, ChevronRight, Share2, ExternalLink, Sparkles,
  AlertCircle, Layout, Server, ArrowRight, Clock, Cpu,
  Layers, Award, BookOpen, Zap, Folder, File, ChevronDown, HelpCircle, ShieldCheck
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  ArchitectureComponent,
  BusinessModule,
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

interface CoreModule {
  name: string;
  iconName: string;
  purpose: string;
  responsibility: string;
  keyFilesFolders: string[];
  dependencies: string[];
}

interface InteractionLink {
  from: string;
  to: string;
  flowDesc: string;
}

interface NonTechnicalOverview {
  projectName: string;
  analogy: string;
  whatItDoes: string;
  whoUsesIt: string[];
  whyItExists: string;
  problemSolved: string;
  solutionProvided: string;
  simpleFeatures: { title: string; desc: string }[];
  coreModules: CoreModule[];
  dependencyMap: { description: string; interactions: InteractionLink[] };
}

function getStringList(value: unknown): string[] {
  if (typeof value === 'string') return value.trim() ? [value] : [];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function getNonTechnicalOverview(repo: Repository): NonTechnicalOverview {
  const executive = repo.overview?.executiveOverview;
  const modules = (Array.isArray(repo.analysis?.businessModules) ? repo.analysis.businessModules : [])
    .filter((module): module is BusinessModule =>
      Boolean(module) && typeof module.name === 'string' && module.name.trim().length > 0
    );
  const moduleNames = new Set(modules.map((module) => module.name.toLocaleLowerCase()));
  const overviewSummary = getEvidenceText(repo.overview?.aiSummary);
  const repositoryDescription = getEvidenceText(repo.description);

  return {
    projectName: repo.fullName || repo.name,
    analogy: UNKNOWN_EVIDENCE,
    whatItDoes: overviewSummary !== UNKNOWN_EVIDENCE ? overviewSummary : repositoryDescription,
    whoUsesIt: getStringList(executive?.who_is_this_for),
    whyItExists: getEvidenceText(executive?.why_was_it_built),
    problemSolved: getEvidenceText(executive?.why_was_it_built),
    solutionProvided: getEvidenceText(executive?.why_is_it_valuable),
    simpleFeatures: Array.isArray(executive?.user_features)
      ? executive.user_features.filter((feature) =>
          feature &&
          typeof feature.name === 'string' &&
          feature.name.trim().length > 0 &&
          typeof feature.description === 'string' &&
          feature.description.trim().length > 0
        ).map((feature) => ({ title: feature.name, desc: feature.description }))
      : [],
    coreModules: modules    .filter((module) =>
      module && typeof module.name === 'string' && module.name.trim().length > 0
    ).map((module) => ({
      name: module.name,
      iconName: 'code',
      purpose: module.purpose || module.description || UNKNOWN_EVIDENCE,
      responsibility: getStringList(module.capabilities).join('; ') || UNKNOWN_EVIDENCE,
      keyFilesFolders: getStringList(module.evidence).length > 0
        ? getStringList(module.evidence)
        : getStringList(module.components),
      dependencies: getStringList(module.connected_modules),
    })),
    dependencyMap: {
      description: getEvidenceText(repo.architecture?.architecture_summary) !== UNKNOWN_EVIDENCE
        ? getEvidenceText(repo.architecture?.architecture_summary)
        : getEvidenceText(repo.architecture?.summary),
      interactions: modules.flatMap((module) =>
        getStringList(module.connected_modules)
          .filter((target) => moduleNames.has(target.toLocaleLowerCase()))
          .map((target) => ({
            from: module.name,
            to: modules.find((candidate) => candidate.name.toLocaleLowerCase() === target.toLocaleLowerCase())?.name || target,
            flowDesc: UNKNOWN_EVIDENCE,
          }))
      ),
    },
  };
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

function getTechName(item: TechItem): string {
  return typeof item === 'string' ? item : item.name;
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

interface ModuleDetailedSpec {
  longDescription: string;
  analogy: string;
  whyCritical: string;
  bestPractices: string[];
  commonTasks: string[];
  mockCodeBlock: string;
  mockCodeLanguage: string;
  executionFlow: string[];
}

function getModuleDetailedSpecs(module: CoreModule): ModuleDetailedSpec {
  return {
    longDescription: module.purpose,
    analogy: UNKNOWN_EVIDENCE,
    whyCritical: UNKNOWN_EVIDENCE,
    bestPractices: [],
    commonTasks: [],
    mockCodeBlock: UNKNOWN_EVIDENCE,
    mockCodeLanguage: '',
    executionFlow: [],
  };
}

const iconMap: Record<string, LucideIcon> = {
  layout: Layout,
  globe: Globe,
  server: Server,
  cpu: Cpu,
  shield: ShieldCheck,
  database: Database,
  zap: Zap,
  folder: Folder,
  terminal: Terminal,
  layers: Layers,
  code: Code,
};

export default function AnalysisDashboard({ repo, isSaved, onSaveToggle, onBackToSearch, onAnalyze, apiAvailable }: AnalysisDashboardProps) {
  const [viewMode, setViewMode] = useState<'overview' | 'modules' | 'analysis'>('overview');
  const [activeTab, setActiveTab] = useState<'architecture' | 'technology' | 'structure' | 'readme'>('architecture');
  const [activeConnectIdx, setActiveConnectIdx] = useState<number | null>(null);
  const [selectedModuleIdx, setSelectedModuleIdx] = useState<number>(0);
  const [hoveredNodeIdx, setHoveredNodeIdx] = useState<number | null>(null);

  useEffect(() => {
    setActiveConnectIdx(null);
    setSelectedModuleIdx(0);
    setHoveredNodeIdx(null);
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

  const overviewData = getNonTechnicalOverview(repo);
  const headerDescription = getEvidenceText(repo.description);
  const architectureData = repo.architecture;
  const architecturePrimarySummary = getEvidenceText(architectureData?.architecture_summary);
  const architectureSummary = architecturePrimarySummary !== UNKNOWN_EVIDENCE
    ? architecturePrimarySummary
    : getEvidenceText(architectureData?.summary);
  const architectureType = getEvidenceText(architectureData?.architecture_type);
  const architectureFlow = getStringList(architectureData?.flow).filter((step) => step !== UNKNOWN_EVIDENCE);
  const requestLifecycle = getStringList(architectureData?.request_lifecycle).filter((step) => step !== UNKNOWN_EVIDENCE);
  const componentCards: ArchitectureComponent[] = (Array.isArray(architectureData?.components) ? architectureData.components : [])
    .filter((component) =>
      Boolean(component) &&
      typeof component.name === 'string' &&
      component.name.trim().length > 0 &&
      typeof component.responsibility === 'string'
    )
    .map((component) => ({
      name: component.name,
      responsibility: component.responsibility,
      connected_to: getStringList(component.connected_to),
      input: getEvidenceText(component.input),
      output: getEvidenceText(component.output),
      communicates_with: getStringList(component.communicates_with),
    }));
  const communicationPatterns = getStringList(architectureData?.communication)
    .filter((pattern) => pattern !== UNKNOWN_EVIDENCE);
  const syncPath = getStringList(architectureData?.sync_path).filter((step) => step !== UNKNOWN_EVIDENCE);
  const asyncPath = getStringList(architectureData?.async_path).filter((step) => step !== UNKNOWN_EVIDENCE);
  const deploymentSummary = getEvidenceText(architectureData?.deployment);
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
  const endUserUseCases = executiveOverview.end_user_use_cases?.length
    ? executiveOverview.end_user_use_cases
    : executiveOverview.typical_use_cases.map((description) => ({ title: '', description, evidence: [] as string[] }));
  const businessModules = (Array.isArray(repo.analysis?.businessModules) ? repo.analysis.businessModules : [])
    .filter((module): module is BusinessModule =>
      Boolean(module) && typeof module.name === 'string' && module.name.trim().length > 0
    )
    .map((module) => ({
      ...module,
      purpose: typeof module.purpose === 'string' ? module.purpose : '',
      description: typeof module.description === 'string' ? module.description : '',
      capabilities: getStringList(module.capabilities),
      components: getStringList(module.components),
      connected_modules: getStringList(module.connected_modules),
      evidence: getStringList(module.evidence),
      confidence: typeof module.confidence === 'number' && Number.isFinite(module.confidence)
        ? module.confidence
        : undefined,
    }));
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

  const findModuleIndex = (moduleName: string) =>
    overviewData.coreModules.findIndex((module) => module.name.toLocaleLowerCase() === moduleName.toLocaleLowerCase());

  const getNodeCoords = (idx: number) => {
    const nodesCount = overviewData.coreModules.length;
    if (nodesCount === 0) return { x: 50, y: 50 };
    if (nodesCount === 4) {
      if (idx === 0) return { x: 25, y: 24 };
      if (idx === 1) return { x: 75, y: 24 };
      if (idx === 2) return { x: 25, y: 76 };
      if (idx === 3) return { x: 75, y: 76 };
    }
    const angle = (idx * 2 * Math.PI) / nodesCount - Math.PI / 2;
    return {
      x: Math.round(50 + 26 * Math.cos(angle)),
      y: Math.round(50 + 26 * Math.sin(angle))
    };
  };

  const handleNodeClick = (nodeIdx: number) => {
    const activeLink = overviewData.dependencyMap.interactions.findIndex((link) => {
      const fromIdx = findModuleIndex(link.from);
      const toIdx = findModuleIndex(link.to);
      return fromIdx === nodeIdx || toIdx === nodeIdx;
    });
    if (activeLink !== -1) {
      setActiveConnectIdx(activeConnectIdx === activeLink ? null : activeLink);
    }
  };

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

      {/* Mode Perspective Selector (Overview vs Modules vs Technical Deep-Dive) */}
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
            onClick={() => setViewMode('modules')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'modules'
                ? 'bg-gradient-to-r from-indigo-500/20 to-purple-600/10 text-indigo-300 border border-indigo-500/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <Layers className="h-4 w-4" />
            <span>📦 Core Modules</span>
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

          <div>
            <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">End User Use Cases</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {endUserUseCases.length > 0 ? endUserUseCases.slice(0, 6).map((useCase, idx) => (
                <div key={`${useCase.title || useCase.description}-${idx}`} className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-5 hover:border-[#8B5CF6]/20 transition-all">
                  <span className="text-[10px] font-mono font-bold text-indigo-400">USE CASE 0{idx + 1}</span>
                  {useCase.title && <h5 className="font-bold text-sm text-white mt-1.5">{useCase.title}</h5>}
                  <p className="text-xs text-gray-400 mt-2 leading-relaxed">{useCase.description}</p>
                  {useCase.evidence && useCase.evidence.length > 0 && (
                    <p className="text-[10px] text-gray-500 mt-3 font-mono break-all">
                      Evidence: {useCase.evidence.slice(0, 2).join(', ')}
                    </p>
                  )}
                </div>
              )) : <p className="text-sm text-gray-400 col-span-full">No sufficiently supported end-user workflows were identified.</p>}
            </div>
          </div>

        </div>
      )}

      {/* -----------------perspective: CORE MODULES BLUEPRINT & INTERACTION GRAPH -----------------*/}
      {viewMode === 'modules' && (
        <div className="space-y-8 animate-fade-in" id="core-modules-frame">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-purple-400 uppercase tracking-wider mb-2">
                <Layers className="h-3.5 w-3.5" />
                <span>Business Module Analyzer</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Core Modules
              </h3>
              <p className="text-xs sm:text-sm text-gray-400 max-w-2xl mt-1.5 leading-relaxed">
                Functional modules are grounded in inspected implementation files. Connection labels appear only when source relationships are verified.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-white/[0.02] border border-white/[0.06] rounded-xl px-3 py-1.5 self-start md:self-auto">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span>{businessModules.length} reported modules</span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" id="core-modules-grid">
            {businessModules.length > 0 ? businessModules.map((module, idx) => (
              <div
                key={`${module.name}-${idx}`}
                className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6 hover:border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/[0.01] transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-purple-400">MODULE 0{idx + 1}</span>
                    <h4 className="text-lg font-black text-white tracking-tight mt-1">{module.name}</h4>
                  </div>
                </div>

                {module.components.length > 0 && <div className="mt-5">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Related Components</h5>
                  <div className="flex flex-wrap gap-2">
                    {module.components.map((component, componentIdx) => (
                      <span key={componentIdx} className="rounded-lg bg-white/[0.04] text-gray-300 border border-white/[0.06] px-2.5 py-1 text-[11px] font-mono break-all">
                        {component}
                      </span>
                    ))}
                  </div>
                </div>}

                {module.connected_modules.length > 0 && <div className="mt-5">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Connected Modules</h5>
                  <div className="flex flex-wrap gap-2">
                    {module.connected_modules.map((connected, connectedIdx) => (
                      <span key={connectedIdx} className="rounded-lg bg-purple-500/10 text-purple-200 border border-purple-500/15 px-2.5 py-1 text-[11px]">
                        {connected}
                      </span>
                    ))}
                  </div>
                </div>}
              </div>
            )) : null}
          </div>
        </div>
      )}

      {false && viewMode === 'modules' && (
        <div className="space-y-10 animate-fade-in" id="core-modules-frame">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-purple-400 uppercase tracking-wider mb-2">
                <Layers className="h-3.5 w-3.5" />
                <span>Repository Blueprint</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Core Modules
              </h3>
              <p className="text-xs sm:text-sm text-gray-400 max-w-2xl mt-1.5 leading-relaxed">
                Understand the primary building blocks of this repository. Learn how they are structured, what responsibilities they hold, and how they interact logistically.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-white/[0.02] border border-white/[0.06] rounded-xl px-3 py-1.5 self-start md:self-auto">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Primary Modules Decoded</span>
            </div>
          </div>

          {/* Modules Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5" id="core-modules-grid">
            {overviewData.coreModules.map((module, mIdx) => {
              const IconComponent = iconMap[module.iconName] || Code;
              const isSelected = selectedModuleIdx === mIdx;
              return (
                <button
                  key={mIdx}
                  onClick={() => setSelectedModuleIdx(mIdx)}
                  className={`group relative text-left flex flex-col justify-between rounded-2xl border p-5 transition-all duration-300 overflow-hidden cursor-pointer w-full bg-transparent ${isSelected
                      ? 'border-purple-500 bg-purple-500/[0.04] shadow-[0_0_20px_rgba(139,92,246,0.15)] scale-[1.02]'
                      : 'border-white/[0.08] bg-white/[0.01] hover:border-white/[0.2] hover:bg-white/[0.02]'
                    }`}
                >
                  {/* Corner gradient glow */}
                  <div className={`absolute -right-8 -top-8 h-20 w-20 rounded-full blur-2xl transition-all duration-300 ${isSelected ? 'bg-purple-500/15' : 'bg-purple-500/0 group-hover:bg-purple-500/5'
                    }`} />

                  <div className="w-full text-left">
                    {/* Card Header */}
                    <div className="flex items-start justify-between gap-3 mb-4">
                      <div className={`h-9 w-9 rounded-xl flex items-center justify-center transition-all duration-300 font-bold uppercase tracking-wider ${isSelected
                          ? 'bg-purple-500/20 text-purple-300 scale-110'
                          : 'bg-purple-500/10 text-purple-400 group-hover:scale-110 group-hover:text-purple-300'
                        }`}>
                        <IconComponent className="h-4.5 w-4.5" />
                      </div>
                      <span className="inline-flex items-center text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border bg-white/[0.04] text-gray-400 border-white/[0.08]">
                        UNIT 0{mIdx + 1}
                      </span>
                    </div>

                    {/* Module Info */}
                    <h4 className={`text-sm font-bold mb-2 leading-snug transition-colors ${isSelected ? 'text-purple-300' : 'text-white group-hover:text-purple-300'
                      }`}>
                      {module.name}
                    </h4>
                    <p className="text-xs text-gray-400 leading-relaxed font-sans mb-3 min-h-[48px]">
                      {module.purpose}
                    </p>

                    {/* Responsibility block with quote design */}
                    <div className="text-[11px] text-gray-300 bg-white/[0.02] border-l-2 border-purple-500/40 pl-2.5 py-1 mb-4 leading-normal italic font-sans font-mono">
                      {module.responsibility}
                    </div>
                  </div>

                  {/* Metadata Section */}
                  <div className="pt-3 border-t border-white/[0.04] space-y-2 w-full text-left">
                    <div>
                      <span className="text-[9px] font-mono uppercase tracking-wider text-gray-500 block">KEY ENVIRONMENT</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {module.keyFilesFolders.slice(0, 3).map((file, fIdx) => (
                          <span
                            key={fIdx}
                            className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-gray-300 border border-white/[0.06]"
                          >
                            {file}
                          </span>
                        ))}
                        {module.keyFilesFolders.length > 3 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.02] text-gray-400 border border-transparent">
                            +{module.keyFilesFolders.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Module Deep-Dive Workspace (EDUCATIONAL WORKBENCH) */}
          {(() => {
            const selectedModule = overviewData.coreModules[selectedModuleIdx] || overviewData.coreModules[0];
            const spec = getModuleDetailedSpecs(selectedModule);
            const SelectedIconComponent = iconMap[selectedModule.iconName] || Code;

            return (
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6 lg:p-8 relative overflow-hidden space-y-8 animate-fade-in" id="module-deep-dive-panel">
                {/* Visual Accent header lines */}
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-500 via-pink-500 to-transparent" />

                {/* Header info */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.06]">
                  <div className="flex items-start gap-4">
                    <div className="h-12 w-12 rounded-xl bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold relative shrink-0">
                      <SelectedIconComponent className="h-6 w-6" />
                      <div className="absolute -inset-1 rounded-xl bg-purple-500/10 blur-md -z-10" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[9px] font-mono text-purple-400 uppercase tracking-widest bg-purple-500/10 px-2 py-0.5 rounded">Deep-Dive Workspace</span>
                        <span className="inline-flex items-center text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border bg-purple-500/10 text-purple-300 border-purple-500/20">
                          Active Component
                        </span>
                      </div>
                      <h4 className="text-xl font-black text-white tracking-tight mt-1 font-sans">{selectedModule.name}</h4>
                      <p className="text-xs text-gray-400 mt-1 max-w-2xl font-sans leading-relaxed">{spec.longDescription}</p>
                    </div>
                  </div>

                  {/* Scope metadata pill board */}
                  <div className="flex flex-wrap gap-4 lg:self-center bg-white/[0.01] border border-white/[0.04] p-3.5 rounded-xl">
                    <div>
                      <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Key Source Tree</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selectedModule.keyFilesFolders.map((file, fIdx) => (
                          <span key={fIdx} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-white border border-white/[0.06]">{file}</span>
                        ))}
                      </div>
                    </div>
                    <div className="border-l border-white/[0.06] pl-4">
                      <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Dependencies</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selectedModule.dependencies.map((dep, dIdx) => (
                          <span key={dIdx} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/15">{dep}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 1 - Analogy & Critical Failure Mode */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* The Analogy panel */}
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 space-y-3 relative overflow-hidden">
                    <div className="absolute top-2 right-2 text-white/[0.02]">
                      <BookOpen className="h-24 w-24" />
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-amber-400 font-sans uppercase tracking-wider">
                      <HelpCircle className="h-4 w-4 shrink-0" />
                      <span>Beginner-Friendly Analogy</span>
                    </div>
                    <p className="text-sm text-gray-300 font-sans leading-relaxed italic pr-4">
                      "{spec.analogy}"
                    </p>
                    <div className="text-[10px] text-gray-500 font-sans">
                      *No repository-grounded analogy is available for this module.
                    </div>
                  </div>

                  {/* Why it is crucial / failure mode panel */}
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 space-y-3 relative overflow-hidden">
                    <div className="absolute top-2 right-2 text-white/[0.02]">
                      <AlertCircle className="h-24 w-24" />
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-rose-400 font-sans uppercase tracking-wider">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>Why is this critical? (Failure Mode)</span>
                    </div>
                    <p className="text-xs text-gray-300 font-sans leading-relaxed">
                      {spec.whyCritical}
                    </p>
                    <div className="text-[10px] text-gray-500 font-sans">
                      *No repository-grounded failure-mode evidence is available for this module.
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 2 - Code Blueprint Draft & Execution Flow Pipeline */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Code blueprint card */}
                  <div className="lg:col-span-7 rounded-xl border border-white/[0.06] bg-[#09090D] overflow-hidden flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.04] bg-white/[0.02]">
                        <div className="flex items-center gap-2">
                          <Code className="h-4 w-4 text-purple-400" />
                          <span className="text-xs font-mono font-bold text-gray-300">Source Code Evidence</span>
                        </div>
                        <span className="text-[10px] font-mono uppercase text-gray-500 px-1.5 py-0.5 rounded bg-white/[0.04]">
                          {spec.mockCodeLanguage}
                        </span>
                      </div>
                      <div className="p-4 overflow-x-auto">
                        <pre className="text-xs font-mono text-gray-300 leading-relaxed max-h-[300px] overflow-y-auto style-scrollbar">
                          <code>{spec.mockCodeBlock}</code>
                        </pre>
                      </div>
                    </div>
                    <div className="px-4 py-2.5 bg-white/[0.01] border-t border-white/[0.04] text-[10px] font-mono text-gray-500 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                      <span>Only code evidence supplied by the repository analysis is shown here.</span>
                    </div>
                  </div>

                  {/* Execution Flow Pipeline card */}
                  <div className="lg:col-span-5 rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 flex flex-col justify-between space-y-4">
                    <div>
                      <div className="flex items-center gap-2 text-xs font-bold text-purple-400 uppercase tracking-wider mb-4">
                        <Zap className="h-4 w-4 shrink-0" />
                        <span>Reported Execution Flow</span>
                      </div>
                      <div className="relative pl-6 space-y-4 border-l border-white/[0.08] ml-2 font-sans text-xs text-left">
                        {spec.executionFlow.map((step, sIdx) => (
                          <div key={sIdx} className="relative">
                            {/* Bullet Dot */}
                            <div className="absolute -left-[30px] top-[2px] h-4 w-4 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center font-mono text-[9px] font-black border border-purple-500/50">
                              {sIdx + 1}
                            </div>
                            <p className="text-white font-medium">{step}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono mt-2 pt-2 border-t border-white/[0.04] text-left">
                      *Only execution steps returned by the repository analysis are shown here.
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 3 - Good Practices & Common Tasks Side-By-Side lists */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                  {/* Good Architectural Practices */}
                  <div className="space-y-3 text-left">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-300 uppercase tracking-wider">
                      <Award className="h-4 w-4 text-purple-400 animate-pulse" />
                      <span>Good Architectural Practices</span>
                    </div>
                    <ul className="space-y-2">
                      {spec.bestPractices.map((practice, pIdx) => (
                        <li key={pIdx} className="flex items-start gap-2 text-xs text-gray-400 leading-normal">
                          <span className="text-purple-400 font-bold shrink-0 mt-0.5">▪</span>
                          <span>{practice}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Common Tasks on this Module */}
                  <div className="space-y-3 text-left">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-300 uppercase tracking-wider">
                      <Terminal className="h-4 w-4 text-purple-400" />
                      <span>Typical Module Responsibilities</span>
                    </div>
                    <ul className="space-y-2">
                      {spec.commonTasks.map((task, tIdx) => (
                        <li key={tIdx} className="flex items-start gap-2 text-xs text-gray-400 leading-normal">
                          <span className="text-purple-400 font-bold shrink-0 mt-0.5">▸</span>
                          <span>{task}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

              </div>
            );
          })()}

          {/* Simplified Dependency Map Component */}
          <div className="rounded-2xl border border-purple-500/15 bg-[#0A0A0E] p-5 sm:p-7 relative overflow-hidden mt-6">
            <div className="absolute top-0 right-0 h-40 w-40 bg-purple-500/[0.02] blur-2xl rounded-full pointer-events-none" />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

              {/* Left Side: Relationship explanations and interactions list */}
              <div className="lg:col-span-5 space-y-4">
                <div>
                  <span className="text-[9px] font-mono text-purple-400 uppercase tracking-widest block mb-1.5">Simplified Data Flows</span>
                  <h4 className="text-base font-extrabold text-white font-sans">Module Interaction Map</h4>
                  <p className="text-xs text-gray-400 leading-relaxed mt-1 font-sans">
                    {overviewData.dependencyMap.description}
                  </p>
                </div>

                <div className="space-y-2">
                  <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Repository-Reported Connections</span>
                  <div className="flex flex-col gap-2">
                    {overviewData.dependencyMap.interactions.length > 0 ? overviewData.dependencyMap.interactions.map((link, idx) => {
                      const isSelected = activeConnectIdx === idx;
                      return (
                        <button
                          key={idx}
                          onClick={() => setActiveConnectIdx(activeConnectIdx === idx ? null : idx)}
                          className={`w-full text-left p-3 rounded-xl border transition-all duration-300 cursor-pointer ${isSelected
                              ? 'bg-purple-500/10 border-purple-500/40 hover:bg-purple-500/15 shadow-[0_0_15px_rgba(139,92,246,0.1)]'
                              : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03] hover:border-white/[0.12]'
                            }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-bold text-white flex items-center gap-1.5 font-sans">
                              <span className={`h-1.5 w-1.5 rounded-full ${isSelected ? 'bg-purple-400 animate-ping' : 'bg-gray-500'}`} />
                              {link.from}
                            </span>
                            <span className="text-[10px] font-mono text-purple-400">&rarr;</span>
                            <span className="text-xs font-bold text-gray-300 font-sans">{link.to}</span>
                          </div>
                          <p className="text-[11px] text-gray-400 leading-normal pl-3 font-sans">
                            {link.flowDesc}
                          </p>
                        </button>
                      );
                    }) : (
                      <p className="rounded-xl border border-dashed border-white/[0.08] p-4 text-xs text-gray-400">
                        {UNKNOWN_EVIDENCE}
                      </p>
                    )}
                  </div>
                </div>

                {/* Connection Evidence Inspector */}
                {activeConnectIdx !== null && overviewData.dependencyMap.interactions[activeConnectIdx] ? (() => {
                  const activeLink = overviewData.dependencyMap.interactions[activeConnectIdx];
                  return (
                    <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 animate-fade-in text-left space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-medium font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase tracking-wider">Analysis Evidence</span>
                        <span className="text-[9px] font-mono text-gray-500">Reported Module Connection</span>
                      </div>
                      <div className="space-y-2 text-xs font-sans">
                        <p className="font-semibold text-white">{activeLink.from} <span className="text-purple-400">&rarr;</span> {activeLink.to}</p>
                        <p className="text-gray-300">{activeLink.flowDesc}</p>
                      </div>
                    </div>
                  );
                })() : (
                  <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.04] text-center">
                    <span className="text-xs text-gray-500 font-sans">Select a reported connection to inspect the available repository evidence.</span>
                  </div>
                )}
              </div>

              {/* Right Side: Beautiful interactive visual graph node model */}
              <div className="lg:col-span-7 bg-black/40 rounded-2xl border border-white/[0.05] p-5 lg:p-7 flex flex-col justify-center min-h-[360px] relative w-full overflow-hidden">
                <span className="text-[9px] font-mono text-gray-500 uppercase tracking-widest block text-center mb-6">Reported Module Relationships</span>

                <div className="grid grid-cols-2 gap-x-8 gap-y-12 max-w-lg mx-auto relative p-6 w-full">

                  {/* Render visual cards nodes */}
                  {overviewData.coreModules.length > 0 ? overviewData.coreModules.map((module, idx) => {
                    const IconComponent = iconMap[module.iconName] || Code;

                    // Check if module is connected in selected link
                    let isSource = false;
                    let isTarget = false;
                    let isAnyActive = activeConnectIdx !== null;

                    if (activeConnectIdx !== null) {
                      const activeLink = overviewData.dependencyMap.interactions[activeConnectIdx];
                      const srcIdx = findModuleIndex(activeLink.from);
                      const dstIdx = findModuleIndex(activeLink.to);
                      isSource = srcIdx === idx;
                      isTarget = dstIdx === idx;
                    }

                    return (
                      <button
                        key={idx}
                        onClick={() => handleNodeClick(idx)}
                        onMouseEnter={() => setHoveredNodeIdx(idx)}
                        onMouseLeave={() => setHoveredNodeIdx(null)}
                        className={`flex flex-col items-center p-4 rounded-xl border text-center transition-all duration-500 relative z-10 w-full cursor-pointer select-none group ${isSource
                            ? 'bg-purple-500/15 border-purple-400 shadow-[0_0_25px_rgba(139,92,246,0.25)] scale-[1.04]'
                            : isTarget
                              ? 'bg-purple-500/10 border-indigo-400 shadow-[0_0_25px_rgba(99,102,241,0.25)] scale-[1.04]'
                              : hoveredNodeIdx === idx
                                ? 'bg-white/[0.04] border-white/[0.2] scale-[1.02]'
                                : isAnyActive
                                  ? 'opacity-40 bg-transparent border-white/[0.03]'
                                  : 'bg-[#0E0E12] border-white/[0.08] hover:border-white/[0.15]'
                          }`}
                      >
                        {/* Sockets */}
                        <div className="absolute top-1/2 -left-1.5 h-3 w-3 rounded-full border border-white/[0.15] bg-[#0A0A0E] flex items-center justify-center -translate-y-1/2">
                          <span className={`h-1.5 w-1.5 rounded-full ${isSource || isTarget ? 'bg-purple-400' : 'bg-gray-700'}`} />
                        </div>
                        <div className="absolute top-1/2 -right-1.5 h-3 w-3 rounded-full border border-white/[0.15] bg-[#0A0A0E] flex items-center justify-center -translate-y-1/2">
                          <span className={`h-1.5 w-1.5 rounded-full ${isSource || isTarget ? 'bg-purple-400' : 'bg-gray-700'}`} />
                        </div>

                        {/* Top decorative bar */}
                        <div className="w-full flex items-center justify-between text-[8px] font-mono text-gray-500 mb-2 pb-1.5 border-b border-white/[0.03]">
                          <span className="tracking-wider uppercase">UNIT_0{idx + 1}</span>
                          <span className="flex items-center gap-1">
                            <span className={`h-1 w-1 rounded-full ${isSource || isTarget ? 'bg-purple-400 animate-ping' : 'bg-emerald-500'}`} />
                            REPORTED
                          </span>
                        </div>

                        {/* Centered Graphic Icon */}
                        <div className={`h-9 w-9 rounded-xl flex items-center justify-center mb-2.5 transition-all duration-500 ${isSource || isTarget
                            ? 'bg-purple-500/25 text-purple-200'
                            : 'bg-white/[0.03] text-gray-400 group-hover:text-white group-hover:bg-white/[0.07]'
                          }`}>
                          <IconComponent className="h-4.5 w-4.5" />
                        </div>

                        <span className="text-[11px] font-extrabold text-white font-mono leading-tight group-hover:text-purple-300 transition-colors">
                          {module.name}
                        </span>

                        <span className="text-[9px] font-mono text-emerald-500 mt-1 uppercase tracking-tight">
                          ANALYZED
                        </span>

                        {/* Bottom alignment badges */}
                        {isSource && (
                          <span className="absolute -bottom-2.5 bg-gradient-to-r from-purple-500 to-indigo-500 text-white text-[8px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-widest scale-90 shadow-md">Source Node</span>
                        )}
                        {isTarget && (
                          <span className="absolute -bottom-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-[8px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-widest scale-90 shadow-md">Receiver Node</span>
                        )}
                      </button>
                    );
                  }) : (
                    <p className="col-span-2 self-center text-center text-xs text-gray-400">{UNKNOWN_EVIDENCE}</p>
                  )}

                  {/* Curving overlay connect vectors map */}
                  <div className="absolute inset-0 pointer-events-none z-0">
                    <svg className="w-full h-full text-white/[0.04]" viewBox="0 0 100 100" preserveAspectRatio="none">
                      <defs>
                        <marker id="arrow-active" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#c084fc" />
                        </marker>
                        <marker id="arrow-inactive" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="rgba(255,255,255,0.15)" />
                        </marker>
                      </defs>

                      {overviewData.dependencyMap.interactions.map((link, idx) => {
                        const fromIdx = findModuleIndex(link.from);
                        const toIdx = findModuleIndex(link.to);
                        const fromCoords = getNodeCoords(fromIdx);
                        const toCoords = getNodeCoords(toIdx);
                        const isActive = activeConnectIdx === idx;
                        const isHovered = hoveredNodeIdx === fromIdx || hoveredNodeIdx === toIdx;

                        const dx = toCoords.x - fromCoords.x;
                        const dy = toCoords.y - fromCoords.y;
                        const midX = (fromCoords.x + toCoords.x) / 2;
                        const midY = (fromCoords.y + toCoords.y) / 2;
                        const len = Math.sqrt(dx * dx + dy * dy) || 1;

                        // Perpendicular curve sag offsets
                        const pullX = midX - (dy / len) * 5;
                        const pullY = midY + (dx / len) * 5;

                        const pathD = `M ${fromCoords.x} ${fromCoords.y} Q ${pullX} ${pullY} ${toCoords.x} ${toCoords.y}`;

                        return (
                          <g key={idx}>
                            {/* Glowing shadow base */}
                            <path
                              d={pathD}
                              fill="none"
                              stroke={isActive ? "rgba(167, 139, 250, 0.2)" : isHovered ? "rgba(255,255,255,0.05)" : "transparent"}
                              strokeWidth={isActive ? "6" : "3"}
                              className="transition-all duration-300"
                            />
                            {/* Core connection track string */}
                            <path
                              d={pathD}
                              fill="none"
                              stroke={isActive ? "#a78bfa" : "rgba(255, 255, 255, 0.08)"}
                              strokeWidth={isActive ? "2" : "1.2"}
                              strokeDasharray={isActive ? "none" : "5,5"}
                              markerEnd={`url(#${isActive ? 'arrow-active' : 'arrow-inactive'})`}
                              className="transition-all duration-300"
                            />
                          </g>
                        );
                      })}
                    </svg>
                  </div>

                </div>

                <div className="mt-8 text-center text-[10px] font-mono text-gray-500">
                  {activeConnectIdx !== null ? (
                    <span className="flex items-center justify-center gap-1.5 text-[#8B5CF6] font-semibold animate-pulse">
                      <Zap className="h-3.5 w-3.5" /> Select another module or reported connection to inspect its evidence
                    </span>
                  ) : (
                    <span>Select a module or connection to highlight relationships reported by the analysis</span>
                  )}
                </div>
              </div>

            </div>
          </div>
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
                      <p className="text-sm text-gray-300 leading-relaxed">{architectureSummary}</p>
                    </div>
                    <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-3 w-full max-w-xs">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-[#c4b5fd]">Inferred Type</div>
                      <div className="mt-1 text-sm font-semibold text-white">{architectureType}</div>
                    </div>
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
                          <p className="text-xs text-gray-300 leading-relaxed">{component.responsibility || UNKNOWN_EVIDENCE}</p>
                          <div className="mt-4 pt-3 border-t border-white/[0.04]">
                            <span className="text-[9px] font-mono uppercase tracking-wider text-gray-500">Connected Components</span>
                            <p className="mt-1 text-[11px] text-gray-400 break-words">
                              {component.connected_to.length > 0 ? component.connected_to.join(', ') : UNKNOWN_EVIDENCE}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01] p-6 text-sm text-gray-400 text-center">
                      {UNKNOWN_EVIDENCE}
                    </div>
                  )}
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
                    )) : (
                      <p className="text-sm text-gray-400 text-center">{UNKNOWN_EVIDENCE}</p>
                    )}
                    <div className="pt-4 border-t border-white/[0.05] space-y-3">
                      <h5 className="text-[10px] font-mono uppercase tracking-widest text-gray-500">Request Lifecycle</h5>
                      {requestLifecycle.length > 0 ? requestLifecycle.map((lifecycleStep, index) => (
                        <div key={`${lifecycleStep}-${index}`} className="rounded-xl border border-white/[0.04] bg-black/30 px-4 py-3 text-xs text-gray-300">
                          {lifecycleStep}
                        </div>
                      )) : (
                        <p className="text-sm text-gray-400">{UNKNOWN_EVIDENCE}</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Core Code Modules */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Core Software Modules Mapping</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {componentCards.length > 0 ? componentCards.map((c, i) => (
                      <div key={`${c.name}-${i}`} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:bg-white/[0.04] hover:border-[#8B5CF6]/25 transition-all">
                        <span className="font-bold text-xs text-white block font-mono truncate">{c.name}</span>
                        <div className="mt-4 space-y-3 text-xs text-gray-300 font-sans">
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Purpose</div>
                            <div className="mt-1 leading-snug">{c.responsibility || UNKNOWN_EVIDENCE}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Input</div>
                            <div className="mt-1 leading-snug">{c.input || UNKNOWN_EVIDENCE}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Output</div>
                            <div className="mt-1 leading-snug">{c.output || UNKNOWN_EVIDENCE}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Communicates With</div>
                            <div className="mt-1 leading-snug text-[#c4b5fd]">
                              {c.communicates_with?.length
                                ? c.communicates_with.join(', ')
                                : c.connected_to.length > 0
                                  ? c.connected_to.join(', ')
                                  : UNKNOWN_EVIDENCE}
                            </div>
                          </div>
                        </div>
                      </div>
                    )) : (
                      <p className="sm:col-span-2 lg:col-span-4 text-sm text-gray-400 text-center">{UNKNOWN_EVIDENCE}</p>
                    )}
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
                      )) : <p>{UNKNOWN_EVIDENCE}</p>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Asynchronous Path</h4>
                    <div className="space-y-3 text-sm text-gray-300">
                      {asyncPath.length > 0 ? asyncPath.map((step, index) => (
                        <div key={`${step}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3">
                          {step}
                        </div>
                      )) : <p>{UNKNOWN_EVIDENCE}</p>}
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
                        <p className="text-sm text-gray-400">{UNKNOWN_EVIDENCE}</p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Deployment Overview</h4>
                    <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-4 text-sm text-gray-200">
                      {deploymentSummary}
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
