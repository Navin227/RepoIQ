export type TechItem = string | {
  name: string;
  source?: string;
  evidence?: string | string[];
  confidence?: number;
  count?: number;
  sources?: string[];
};

export interface TechStack {
  frontend: TechItem[];
  backend: TechItem[];
  database: TechItem[];
  infrastructure: TechItem[];
  devops: TechItem[];
  cloud?: TechItem[];
  messaging?: TechItem[];
  monitoring?: TechItem[];
  cicd?: TechItem[];
  tooling?: TechItem[];
}

export interface RawTechStack {
  categories?: Partial<TechStack>;
  flat?: Partial<TechStack>;
  languages?: string[];
}

export interface FileTreeNode {
  name: string;
  type: "file" | "folder";
  children?: FileTreeNode[];
  size?: string;
}

export interface Repository {
  owner: string;
  name: string;
  fullName: string;
  description: string;
  stars?: number;
  forks?: number;
  language?: string;
  topics?: string[];
  url: string;
  localPath?: string;
  readme?: string;
  readmePath?: string;
  overview: {
    aiSummary: string;
    executiveOverview?: ExecutiveOverview;
    info?: {
      license: string;
      contributors: number;
      openIssues: number;
      lastCommit: string;
    };
    stats?: {
      linesOfCode: string;
      filesCount: number;
      commitsCount: string;
      pullRequests: number;
    };
    topics?: string[];
  };
  analysis: {
    projectSummary: string;
    techStack: TechStack;
    keyFeatures: string[];
    businessModules?: BusinessModule[];
  };
  folderStructure: FileTreeNode[];
  similarRepos: SimilarRepo[];
  languages?: string[];
  rawStack?: RawTechStack;
  architecture?: ArchitectureAnalysis;
  analysisEvidence?: Record<string, unknown>;
  analysisStatus?: string;
  analysisError?: string;
  commitSha?: string;
  repositoryModel?: Record<string, unknown>;
  analysisRunId?: string;
}

export interface ArchitectureComponent {
  name: string;
  responsibility: string;
  connected_to: string[];
  input?: string;
  output?: string;
  communicates_with?: string[];
  connection_evidence_status?: 'verified' | 'verified_none' | 'not_fully_assessed' | string;
}

export interface ArchitectureAnalysis {
  architecture_summary: string;
  summary?: string;
  architecture_type: string;
  flow: string[];
  request_lifecycle: string[];
  components: ArchitectureComponent[];
  communication: string[];
  deployment: string;
  sync_path?: string[];
  async_path?: string[];
}

export interface ExecutiveOverview {
  what_is_this_project: string[];
  why_was_it_built: string;
  user_features: Array<{
    name: string;
    description: string;
    evidence?: string[];
  }>;
  typical_use_cases: string[];
  end_user_use_cases?: Array<{
    title: string;
    description: string;
    evidence?: string[];
  }>;
  who_is_this_for: string[];
  why_is_it_valuable: string;
  one_line_summary: string;
}

export interface BusinessModule {
  name: string;
  purpose: string;
  description?: string;
  capabilities: string[];
  components: string[];
  connected_modules: string[];
  connection_evidence_status?: 'verified' | 'verified_none' | 'not_fully_assessed';
  confidence?: number;
  evidence?: string[];
}

export interface SimilarRepo {
  name?: string;
  owner?: string;
  fullName: string;
  full_name?: string;
  url?: string;
  html_url?: string;
  description: string;
  stars: number;
  forks: number;
  language: string;
  topics: string[];
  similarity?: number;
  similarity_breakdown?: Record<string, number>;
  relevance_score?: number;
  analyzability_score?: number | null;
  ranking_score?: number | null;
  ranking_adjustment?: number | null;
  comparable_relevance_cohort?: boolean | null;
  tree_inspection_state?: string;
  tree_truncated?: boolean;
  evidence_readiness?: string;
  readiness_reason?: string;
  repository_type?: string;
  inspected_file_count?: number;
  tree_reported_file_count?: number;
  meaningful_source_file_count?: number;
  reason?: string;
  project_type?: string;
  architecture?: string;
  shared_technologies?: string[];
  shared_modules?: string[];
  badges?: string[];
}

export interface AnalysisResult {
  status: "analyzing" | "success" | "error";
  repoName?: string;
  repoUrl?: string;
  localPath?: string;
  readme?: string;
  readmePath?: string;
  stack?: {
    categories?: Partial<TechStack>;
    flat?: TechStack;
  };
  folderStructure?: FileTreeNode[];
  projectSummary?: string;
  keyFeatures?: string[];
  overview?: string;
  executive_overview?: ExecutiveOverview;
  architecture?: ArchitectureAnalysis;
  architecture_summary?: string;
  modules?: BusinessModule[];
  ai_insights?: string[];
  similar_repositories?: SimilarRepo[];
  analysis_evidence?: Record<string, unknown>;
  analysis_status?: string;
  commit_sha?: string;
  repository_model?: Record<string, unknown>;
  coverage_manifest?: Record<string, unknown>;
  report_sections?: Record<string, unknown>;
  languages?: string[]; // Add languages
  error?: string;
  analysis_run_id?: string;
}
