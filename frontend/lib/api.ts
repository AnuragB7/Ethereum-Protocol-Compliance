import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Default timeout for most API calls (30 seconds)
const DEFAULT_TIMEOUT = 30000;

// Extended timeout for long-running operations like PR analysis (10 minutes)
const EXTENDED_TIMEOUT = 600000;

export const api = axios.create({
  baseURL: API_URL,
  timeout: DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create a separate instance for long-running operations
export const apiLongRunning = axios.create({
  baseURL: API_URL,
  timeout: EXTENDED_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API Configuration
export interface APIConfig {
  provider: 'openai' | 'anthropic';
  api_key: string;
  api_base?: string;  // Required for OpenAI, optional for Anthropic
  llm_model?: string;
  embed_model?: string;
  embed_api_key?: string;  // Separate key for embeddings (useful for Anthropic)
  embed_api_base?: string;  // Separate base for embeddings
}

export const configureAPI = async (config: APIConfig) => {
  const response = await api.post('/api/config', config);
  return response.data;
};

// Get available providers
export const getProviders = async () => {
  const response = await api.get('/api/config/providers');
  return response.data;
};

// Upload codebase
export const uploadCodebase = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/api/upload-codebase', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Upload folder (uses extended timeout for large codebases)
export const uploadFolder = async (path: string) => {
  const response = await apiLongRunning.post('/api/upload-folder', null, {
    params: { codebase_path: path },
  });
  return response.data;
};

// Reset graph data
export const resetGraph = async () => {
  const response = await api.post('/api/reset');
  return response.data;
};

// Query
export const queryCodebase = async (question: string) => {
  const response = await api.post('/api/query', { query: question });
  return response.data;
};

// Get entities
export const getEntities = async () => {
  const response = await api.get('/api/entities');
  return response.data;
};

// Get entity details
export const getEntity = async (entityName: string) => {
  const response = await api.get(`/api/entities/${entityName}`);
  return response.data;
};

// Analyze function
export const analyzeFunction = async (functionName: string) => {
  const response = await api.post('/api/analyze/function', {
    function_name: functionName,
  });
  return response.data;
};

// Analyze module
export const analyzeModule = async (filePath: string) => {
  const response = await api.post('/api/analyze/module', {
    file_path: filePath,
  });
  return response.data;
};

// Analyze codebase
export const analyzeCodebase = async () => {
  const response = await api.get('/api/analyze/codebase');
  return response.data;
};

// Generate test cases
export const generateTests = async (functionName: string, count: number = 5) => {
  const response = await api.post('/api/tests/generate', {
    function_name: functionName,
    count,
  });
  return response.data;
};

// Generate Selenium tests
export const generateSeleniumTests = async (
  functionName: string,
  baseUrl: string = 'http://localhost:3000'
) => {
  const response = await api.post('/api/tests/selenium', {
    function_name: functionName,
    base_url: baseUrl,
  });
  return response.data;
};

// Generate unit tests
export const generateUnitTests = async (functionName: string) => {
  const response = await api.post('/api/tests/unit', {
    function_name: functionName,
  });
  return response.data;
};

// Get call chain
export const getCallChain = async (functionName: string, depth: number = 3) => {
  const response = await api.get(`/api/call-chain/${functionName}`, {
    params: { depth },
  });
  return response.data;
};

// Get graph data
export const getGraphData = async () => {
  const response = await api.get('/api/graph-data');
  return response.data;
};

// Get graph data from specific storage (local or PR)
export const getGraphDataFromStorage = async (source: 'local' | 'pr', prGraphId?: string) => {
  if (source === 'pr' && prGraphId) {
    const response = await api.get(`/api/pr-analysis/graphs/${prGraphId}/data`);
    return response.data;
  }
  // Default to local graph_storage
  const response = await api.get('/api/graph-data');
  return response.data;
};

// Get statistics
export const getStatistics = async () => {
  const response = await api.get('/api/statistics');
  return response.data;
};

// Health check
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ============================================================================
// ETHEREUM COMPLIANCE API
// ============================================================================

// Specification Management

// List all specifications
export const listSpecifications = async () => {
  const response = await api.get('/api/specs/list');
  return response.data;
};

// Upload a specification file
export const uploadSpecification = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/api/specs/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Add a custom rule
export const addCustomRule = async (rule: {
  id: string;
  source: string;
  category: string;
  severity: string;
  description: string;
  patterns?: string[];
  must_contain?: string[];
  must_not_contain?: string[];
  recommendation?: string;
  languages?: string[];
}) => {
  const response = await api.post('/api/specs/add-rule', rule);
  return response.data;
};

// Fetch an EIP
export const fetchEIP = async (eipNumber: number, loadRules: boolean = true) => {
  const response = await api.get(`/api/specs/eip/${eipNumber}`, {
    params: { load_rules: loadRules },
  });
  return response.data;
};

// Search EIPs
export const searchEIPs = async (query: string) => {
  const response = await api.get('/api/specs/eip/search', {
    params: { query },
  });
  return response.data;
};

// Get compliance rules
export const getComplianceRules = async (params?: {
  source?: string;
  category?: string;
  severity?: string;
  language?: string;
}) => {
  const response = await api.get('/api/specs/rules', { params });
  return response.data;
};

// Compliance Checking

// Check compliance
export const checkCompliance = async (params?: {
  entity_name?: string;
  file_path?: string;
  rule_ids?: string[];
  severity_filter?: string;
}) => {
  const response = await api.post('/api/compliance/check', params || {});
  return response.data;
};

// Get compliance report
export const getComplianceReport = async () => {
  const response = await api.get('/api/compliance/report');
  return response.data;
};

// Get compliance deviations
export const getComplianceDeviations = async (params?: {
  severity?: string;
  category?: string;
  file_path?: string;
}) => {
  const response = await api.get('/api/compliance/deviations', { params });
  return response.data;
};

// Get compliance summary
export const getComplianceSummary = async () => {
  const response = await api.get('/api/compliance/summary');
  return response.data;
};

// Git Analysis

// Analyze local commit
export const analyzeCommit = async (repoPath: string, commitHash: string = 'HEAD') => {
  const response = await api.post('/api/compliance/analyze-commit', {
    repo_path: repoPath,
    commit_hash: commitHash,
  });
  return response.data;
};

// Analyze remote commit
export const analyzeRemoteCommit = async (repoUrl: string, commitHash: string) => {
  const response = await api.post('/api/compliance/analyze-remote-commit', {
    repo_url: repoUrl,
    commit_hash: commitHash,
  });
  return response.data;
};

// Analyze pull request
export const analyzePullRequest = async (
  owner: string,
  repo: string,
  prNumber: number,
  token?: string
) => {
  const response = await api.post('/api/compliance/analyze-pr', {
    owner,
    repo,
    pr_number: prNumber,
    token,
  });
  return response.data;
};

// Analyze commit range
export const analyzeCommitRange = async (
  repoPath: string,
  fromCommit: string,
  toCommit: string = 'HEAD'
) => {
  const response = await api.post('/api/compliance/analyze-commit-range', null, {
    params: {
      repo_path: repoPath,
      from_commit: fromCommit,
      to_commit: toCommit,
    },
  });
  return response.data;
};

// =============================================================================
// LLM Compliance (Qdrant Hybrid Search + LLM Analysis)
// =============================================================================

// Clone ethereum/execution-specs from GitHub
// Uses extended timeout since cloning can take time
export const cloneSpecs = async (branch: string = 'forks/amsterdam', force: boolean = false) => {
  const response = await apiLongRunning.post('/api/llm-compliance/clone-specs', { branch, force });
  return response.data;
};

// Ingest specifications into Qdrant
// Uses extended timeout since ingestion can take several minutes
export const ingestSpecs = async (forks?: string[], includeDocs: boolean = true) => {
  const response = await apiLongRunning.post('/api/llm-compliance/ingest-specs', {
    forks,
    include_docs: includeDocs,
  });
  return response.data;
};

// Get spec index statistics
export const getSpecStats = async () => {
  const response = await api.get('/api/llm-compliance/spec-stats');
  return response.data;
};

// Query specifications using hybrid search
export const querySpecs = async (query: string, topK: number = 5, alpha: number = 0.5) => {
  const response = await api.post('/api/llm-compliance/query-specs', {
    query,
    top_k: topK,
    alpha,
  });
  return response.data;
};

// Search specifications by EIP number
export const searchSpecsByEIP = async (eipNumber: string, topK: number = 10) => {
  const response = await api.get(`/api/llm-compliance/search-eip/${eipNumber}`, {
    params: { top_k: topK },
  });
  return response.data;
};

// Run LLM compliance check on codebase
// Uses extended timeout since compliance checks can take several minutes
export const runLLMCompliance = async (
  maxEntities: number = 20, 
  specTopK: number = 5, 
  codebasePath?: string
) => {
  const response = await apiLongRunning.post('/api/llm-compliance/run-compliance', {
    max_entities: maxEntities,
    spec_top_k: specTopK,
    codebase_path: codebasePath || null,
  });
  return response.data;
};

// Analyze a code snippet for compliance
export const analyzeCodeForCompliance = async (
  code: string,
  language: string = 'go',
  entityName: string = 'snippet'
) => {
  const response = await api.post('/api/llm-compliance/analyze-code', {
    code,
    language,
    entity_name: entityName,
  });
  return response.data;
};

// Reset specification index
export const resetSpecs = async () => {
  const response = await api.post('/api/llm-compliance/reset-specs');
  return response.data;
};

// Get available forks from cloned specs
export const getAvailableForks = async () => {
  const response = await api.get('/api/llm-compliance/available-forks');
  return response.data;
};

// =============================================================================
// PR Analysis (Dual-Mode: Quick + Deep)
// =============================================================================

export interface PRAnalysisRequest {
  owner: string;
  repo: string;
  pr_number: number;
  mode: 'quick' | 'deep' | 'both';
  github_token?: string;
}

export interface GraphStats {
  total_entities: number;
  total_relationships: number;
  total_files: number;
  languages: string[];
  entity_types: Record<string, number>;
  relationship_types: Record<string, number>;
}

export interface PRCommit {
  sha: string;
  full_sha?: string;
  message: string;
  author: string;
}

export interface PRAnalysisResult {
  pr: string;
  timestamp: string;
  commit_sha?: string;
  base_sha?: string;
  graph_id?: string;  // ID for accessing persisted graph
  quick?: {
    mode: string;
    success: boolean;
    duration_seconds: number;
    deviations: any[];
    files_analyzed: number;
    critical_count: number;
    warning_count: number;
    error?: string;
    commit_sha?: string;
    commits?: PRCommit[];
    total_commits?: number;
    analysis_note?: string;
  };
  deep?: {
    mode: string;
    success: boolean;
    duration_seconds: number;
    deviations: any[];
    entities_analyzed: number;
    files_analyzed: number;
    critical_count: number;
    warning_count: number;
    error?: string;
    commit_sha?: string;
    graph_stats?: GraphStats;
    graph_persisted?: boolean;
    commits?: PRCommit[];
    total_commits?: number;
    analysis_note?: string;
  };
  combined_deviations: any[];
  total_critical: number;
  total_warning: number;
  compliance_passed: boolean;
}

export interface PRGraphMetadata {
  id: string;
  owner: string;
  repo: string;
  pr_number: number;
  commit_sha: string;
  timestamp: string;
  stats: GraphStats;
}

// Analyze a GitHub PR with dual-mode support (synchronous)
// Use this for quick analysis only - for deep/both, use async version
export const analyzePRDualMode = async (request: PRAnalysisRequest): Promise<PRAnalysisResult> => {
  const response = await apiLongRunning.post('/api/pr-analysis/analyze', request);
  return response.data;
};

// =============================================================================
// Async Analysis (for deep/long-running analysis)
// =============================================================================

export interface AsyncAnalysisResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  owner: string;
  repo: string;
  pr_number: number;
  mode: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  result?: PRAnalysisResult;
  error?: string;
}

// Start async PR analysis (for deep/both modes)
// Uses extended timeout because initialization may take time on first call
export const startPRAnalysisAsync = async (request: PRAnalysisRequest): Promise<AsyncAnalysisResponse> => {
  const response = await apiLongRunning.post('/api/pr-analysis/analyze-async', request);
  return response.data;
};

// Get job status
export const getJobStatus = async (jobId: string): Promise<JobStatusResponse> => {
  const response = await api.get(`/api/pr-analysis/jobs/${jobId}`);
  return response.data;
};

// List all jobs
export const listJobs = async (): Promise<{ jobs: any[]; total: number }> => {
  const response = await api.get('/api/pr-analysis/jobs');
  return response.data;
};

// Delete a job
export const deleteJob = async (jobId: string): Promise<void> => {
  await api.delete(`/api/pr-analysis/jobs/${jobId}`);
};

// =============================================================================
// PR Graph Management
// =============================================================================

// List all persisted PR graphs
export const listPRGraphs = async (): Promise<{ total: number; graphs: PRGraphMetadata[] }> => {
  const response = await api.get('/api/pr-analysis/graphs');
  return response.data;
};

// Get PR graph data
export const getPRGraphData = async (prId: string): Promise<{ nodes: any[]; edges: any[] }> => {
  const response = await api.get(`/api/pr-analysis/graphs/${prId}`);
  return response.data;
};

// Delete a PR graph
export const deletePRGraph = async (prId: string): Promise<void> => {
  await api.delete(`/api/pr-analysis/graphs/${prId}`);
};

// Load PR graph to main storage (makes it visible in Statistics tab)
export const loadPRGraphToMain = async (prId: string): Promise<void> => {
  await api.post(`/api/pr-analysis/graphs/${prId}/load`);
};

// Parse a GitHub PR URL to extract owner, repo, and PR number
export const parsePRUrl = (url: string): { owner: string; repo: string; prNumber: number } | null => {
  // Match patterns like:
  // https://github.com/owner/repo/pull/123
  // github.com/owner/repo/pull/123
  const match = url.match(/(?:https?:\/\/)?github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
  if (match) {
    return {
      owner: match[1],
      repo: match[2],
      prNumber: parseInt(match[3], 10)
    };
  }
  return null;
};
