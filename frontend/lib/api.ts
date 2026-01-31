import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API Configuration
export const configureAPI = async (config: {
  api_key: string;
  api_base: string;
  llm_model?: string;
  embed_model?: string;
}) => {
  const response = await api.post('/api/config', config);
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

// Upload folder
export const uploadFolder = async (path: string) => {
  const response = await api.post('/api/upload-folder', null, {
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
export const cloneSpecs = async (branch: string = 'forks/amsterdam', force: boolean = false) => {
  const response = await api.post('/api/llm-compliance/clone-specs', { branch, force });
  return response.data;
};

// Ingest specifications into Qdrant
export const ingestSpecs = async (forks?: string[], includeDocs: boolean = true) => {
  const response = await api.post('/api/llm-compliance/ingest-specs', {
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
export const runLLMCompliance = async (maxEntities: number = 20, specTopK: number = 5) => {
  const response = await api.post('/api/llm-compliance/run-compliance', {
    max_entities: maxEntities,
    spec_top_k: specTopK,
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
