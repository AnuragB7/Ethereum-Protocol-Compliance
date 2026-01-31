'use client';

import React, { useState, useEffect } from 'react';
import {
  GitPullRequest,
  Play,
  Loader,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Clock,
  FileCode,
  Zap,
  Search,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Database,
  ArrowRight,
  BarChart3,
  GitBranch,
  Download,
  FolderCode,
  Upload
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { 
  analyzePRDualMode, 
  parsePRUrl, 
  PRAnalysisResult, 
  getSpecStats, 
  loadPRGraphToMain,
  startPRAnalysisAsync,
  getJobStatus,
  JobStatusResponse,
  runLLMCompliance
} from '../lib/api';

interface Deviation {
  rule_id?: string;
  severity: string;
  description: string;
  file?: string;
  line?: number;
  recommendation?: string;
  spec_reference?: string;
  explanation?: string;
  code_location?: string;
  commit_sha?: string;
  entity_name?: string;
}

interface GraphStatsProps {
  stats: {
    total_entities: number;
    total_relationships: number;
    total_files: number;
    languages: string[];
    entity_types: Record<string, number>;
    relationship_types: Record<string, number>;
  };
  graphId?: string;
  graphPersisted?: boolean;
}

function GraphStatsCard({ stats, graphId, graphPersisted }: GraphStatsProps) {
  const [loadingToMain, setLoadingToMain] = useState(false);
  const [loadedToMain, setLoadedToMain] = useState(false);

  const handleLoadToMain = async () => {
    if (!graphId) return;
    
    setLoadingToMain(true);
    try {
      await loadPRGraphToMain(graphId);
      setLoadedToMain(true);
    } catch (err) {
      console.error('Failed to load graph to main:', err);
    } finally {
      setLoadingToMain(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-purple-600" />
          <h3 className="text-lg font-semibold">Code Graph Statistics</h3>
        </div>
        {graphPersisted && graphId && (
          <button
            onClick={handleLoadToMain}
            disabled={loadingToMain || loadedToMain}
            className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm transition ${
              loadedToMain 
                ? 'bg-green-100 text-green-700 cursor-default'
                : 'bg-purple-600 text-white hover:bg-purple-700 disabled:bg-gray-400'
            }`}
          >
            {loadingToMain ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Loading...
              </>
            ) : loadedToMain ? (
              <>
                <CheckCircle className="w-4 h-4" />
                Loaded to Statistics
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Load to Statistics Tab
              </>
            )}
          </button>
        )}
      </div>
      
      {/* Main Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-purple-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-purple-700">{stats.total_entities}</div>
          <div className="text-sm text-purple-600">Entities</div>
        </div>
        <div className="bg-blue-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-blue-700">{stats.total_relationships}</div>
          <div className="text-sm text-blue-600">Relationships</div>
        </div>
        <div className="bg-green-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-green-700">{stats.total_files}</div>
          <div className="text-sm text-green-600">Files</div>
        </div>
        <div className="bg-amber-50 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-amber-700">{stats.languages.length}</div>
          <div className="text-sm text-amber-600">Languages</div>
        </div>
      </div>
      
      {/* Breakdown */}
      <div className="grid grid-cols-2 gap-6">
        {/* By Entity Type */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">By Entity Type</h4>
          <div className="space-y-2">
            {Object.entries(stats.entity_types).map(([type, count]) => (
              <div key={type} className="flex justify-between items-center">
                <span className="text-sm text-gray-600 capitalize">{type.replace('_', ' ')}</span>
                <span className="text-sm font-medium bg-gray-100 px-2 py-0.5 rounded">{count}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* By Language */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Languages</h4>
          <div className="flex flex-wrap gap-2">
            {stats.languages.map((lang) => (
              <span 
                key={lang} 
                className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm capitalize"
              >
                {lang}
              </span>
            ))}
          </div>
          
          {Object.keys(stats.relationship_types).length > 0 && (
            <>
              <h4 className="text-sm font-medium text-gray-700 mb-2 mt-4">Relationship Types</h4>
              <div className="space-y-1">
                {Object.entries(stats.relationship_types).map(([type, count]) => (
                  <div key={type} className="flex justify-between items-center text-sm">
                    <span className="text-gray-600">{type}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      
      {/* Graph persisted note */}
      {graphPersisted && (
        <div className="mt-4 pt-4 border-t text-sm text-gray-500 flex items-center gap-2">
          <Database className="w-4 h-4" />
          Graph data saved. Click "Load to Statistics Tab" to visualize the code graph.
        </div>
      )}
    </div>
  );
}

export default function PRAnalysisView() {
  // Analysis source - 'pr' for GitHub PR, 'uploaded' for already indexed codebase
  const [analysisSource, setAnalysisSource] = useState<'pr' | 'uploaded'>('pr');
  
  // Input state
  const [prUrl, setPrUrl] = useState('');
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [prNumber, setPrNumber] = useState<number | ''>('');
  const [mode, setMode] = useState<'quick' | 'deep' | 'both'>('quick');
  const [githubToken, setGithubToken] = useState('');
  const [useUrlInput, setUseUrlInput] = useState(true);
  
  // Uploaded code analysis state
  const [uploadedAnalysisLoading, setUploadedAnalysisLoading] = useState(false);
  const [uploadedMaxEntities, setUploadedMaxEntities] = useState(20);
  
  // Result state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PRAnalysisResult | null>(null);
  const [expandedDeviations, setExpandedDeviations] = useState<Set<number>>(new Set());
  
  // Async job state (for deep/both analysis)
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  
  // Spec status
  const [specsIndexed, setSpecsIndexed] = useState<boolean | null>(null);
  const [specCount, setSpecCount] = useState(0);
  
  // Check spec status on mount
  useEffect(() => {
    checkSpecStatus();
  }, []);
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);
  
  // Parse URL when it changes
  useEffect(() => {
    if (useUrlInput && prUrl) {
      const parsed = parsePRUrl(prUrl);
      if (parsed) {
        setOwner(parsed.owner);
        setRepo(parsed.repo);
        setPrNumber(parsed.prNumber);
        setError('');
      }
    }
  }, [prUrl, useUrlInput]);
  
  const checkSpecStatus = async () => {
    try {
      const response = await getSpecStats();
      const indexed = response.stats?.indexed || false;
      const chunks = response.stats?.total_chunks || 0;
      setSpecsIndexed(indexed);
      setSpecCount(chunks);
    } catch (err) {
      setSpecsIndexed(false);
      setSpecCount(0);
    }
  };
  
  const pollJobStatus = async (id: string) => {
    try {
      const status = await getJobStatus(id);
      setJobStatus(status);
      
      if (status.status === 'completed' && status.result) {
        // Job completed - set result and stop polling
        setResult(status.result);
        setLoading(false);
        setJobId(null);
        setJobStatus(null);
        if (pollingInterval) {
          clearInterval(pollingInterval);
          setPollingInterval(null);
        }
      } else if (status.status === 'failed') {
        // Job failed - show error and stop polling
        setError(status.error || 'Analysis failed');
        setLoading(false);
        setJobId(null);
        setJobStatus(null);
        if (pollingInterval) {
          clearInterval(pollingInterval);
          setPollingInterval(null);
        }
      }
      // If still running or pending, keep polling
    } catch (err: any) {
      console.error('Failed to poll job status:', err);
    }
  };

  const handleAnalyze = async () => {
    if (!owner || !repo || !prNumber) {
      setError('Please provide owner, repo, and PR number');
      return;
    }
    
    setLoading(true);
    setError('');
    setResult(null);
    setJobId(null);
    setJobStatus(null);
    
    // Clear any existing polling
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    
    try {
      // For quick mode, use synchronous API
      if (mode === 'quick') {
        const response = await analyzePRDualMode({
          owner,
          repo,
          pr_number: Number(prNumber),
          mode,
          github_token: githubToken || undefined
        });
        setResult(response);
        setLoading(false);
      } else {
        // For deep or both mode, use async API with polling
        const asyncResponse = await startPRAnalysisAsync({
          owner,
          repo,
          pr_number: Number(prNumber),
          mode,
          github_token: githubToken || undefined
        });
        
        setJobId(asyncResponse.job_id);
        
        // Start polling for job status every 3 seconds
        const interval = setInterval(() => {
          pollJobStatus(asyncResponse.job_id);
        }, 3000);
        setPollingInterval(interval);
        
        // Do initial poll immediately
        await pollJobStatus(asyncResponse.job_id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed');
      setLoading(false);
    }
  };
  
  const handleCancelAnalysis = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setLoading(false);
    setJobId(null);
    setJobStatus(null);
  };

  // Handle uploaded code compliance analysis
  const handleUploadedCodeAnalysis = async () => {
    setUploadedAnalysisLoading(true);
    setError('');
    setResult(null);
    
    try {
      const response = await runLLMCompliance(uploadedMaxEntities, 5);
      
      // Convert to PRAnalysisResult format for consistent display
      const report = response.report;
      const convertedResult: PRAnalysisResult = {
        pr: 'Uploaded Codebase',
        timestamp: report.timestamp,
        deep: {
          mode: 'deep',
          success: true,
          duration_seconds: 0,
          deviations: report.deviations || [],
          entities_analyzed: report.total_entities_analyzed || 0,
          files_analyzed: 0,
          critical_count: report.critical_count || 0,
          warning_count: report.warning_count || 0,
        },
        combined_deviations: report.deviations || [],
        total_critical: report.critical_count || 0,
        total_warning: report.warning_count || 0,
        compliance_passed: (report.critical_count || 0) === 0,
      };
      setResult(convertedResult);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed');
    } finally {
      setUploadedAnalysisLoading(false);
    }
  };
  
  const toggleDeviation = (index: number) => {
    const newExpanded = new Set(expandedDeviations);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedDeviations(newExpanded);
  };
  
  const getSeverityIcon = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      default:
        return <Info className="w-5 h-5 text-blue-500" />;
    }
  };
  
  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-100 text-red-800 border-red-200',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      info: 'bg-blue-100 text-blue-800 border-blue-200'
    };
    return colors[severity?.toLowerCase()] || colors.info;
  };
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitPullRequest className="w-8 h-8 text-purple-600" />
          <div>
            <h2 className="text-2xl font-bold text-gray-900">LLM Compliance Analysis</h2>
            <p className="text-gray-600">Analyze code for Ethereum protocol compliance</p>
          </div>
        </div>
        
        {/* Spec Status Badge */}
        <div className="flex items-center gap-2">
          {specsIndexed === null ? (
            <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm flex items-center gap-2">
              <Loader className="w-4 h-4 animate-spin" />
              Checking specs...
            </span>
          ) : specsIndexed ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm flex items-center gap-2">
              <Database className="w-4 h-4" />
              {specCount.toLocaleString()} specs indexed
            </span>
          ) : (
            <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Specs not indexed
            </span>
          )}
        </div>
      </div>
      
      {/* Spec Not Indexed Warning */}
      {specsIndexed === false && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-600" />
            <div>
              <div className="font-medium text-amber-800">Ethereum Specifications Not Indexed</div>
              <div className="text-sm text-amber-700">
                For full compliance analysis, ingest the Ethereum execution specs first.
              </div>
            </div>
          </div>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              // Navigate to Specifications tab to set up specs
              window.dispatchEvent(new CustomEvent('navigate', { detail: 'specs' }));
            }}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 flex items-center gap-2 transition"
          >
            Go to Specifications
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      )}
      
      {/* Analysis Source Selector */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-gray-600">Analyze:</span>
          <button
            onClick={() => { setAnalysisSource('pr'); setResult(null); setError(''); }}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-2 ${
              analysisSource === 'pr'
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <GitPullRequest className="w-4 h-4" />
            GitHub Pull Request
          </button>
          <button
            onClick={() => { setAnalysisSource('uploaded'); setResult(null); setError(''); }}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-2 ${
              analysisSource === 'uploaded'
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <Upload className="w-4 h-4" />
            Uploaded Code
          </button>
        </div>
      </div>
      
      {/* Uploaded Code Analysis Section */}
      {analysisSource === 'uploaded' && (
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">Analyze Uploaded Codebase</h3>
            <p className="text-sm text-gray-600 mb-4">
              Run LLM-powered compliance analysis on the code you uploaded via the Upload tab.
              This analyzes the indexed code graph against Ethereum specifications.
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">
              Max Entities to Analyze:
            </label>
            <input
              type="number"
              min="1"
              max="100"
              value={uploadedMaxEntities}
              onChange={(e) => setUploadedMaxEntities(parseInt(e.target.value) || 20)}
              className="w-24 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
            />
            <span className="text-xs text-gray-500">
              (Higher = more comprehensive but slower)
            </span>
          </div>
          
          <button
            onClick={handleUploadedCodeAnalysis}
            disabled={uploadedAnalysisLoading || !specsIndexed}
            className="w-full py-3 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {uploadedAnalysisLoading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Analyzing Codebase...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Run Compliance Check
              </>
            )}
          </button>
          
          {!specsIndexed && (
            <p className="text-sm text-amber-600">
              Please index specifications first (Specifications tab → Qdrant Index)
            </p>
          )}
        </div>
      )}
      
      {/* PR Input Section */}
      {analysisSource === 'pr' && (
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={() => setUseUrlInput(true)}
            className={`px-4 py-2 rounded-lg transition ${
              useUrlInput 
                ? 'bg-purple-100 text-purple-700 font-medium' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Paste PR URL
          </button>
          <button
            onClick={() => setUseUrlInput(false)}
            className={`px-4 py-2 rounded-lg transition ${
              !useUrlInput 
                ? 'bg-purple-100 text-purple-700 font-medium' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Manual Input
          </button>
        </div>
        
        {useUrlInput ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              GitHub PR URL
            </label>
            <input
              type="text"
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/123"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
            {prUrl && owner && repo && prNumber && (
              <div className="mt-2 text-sm text-green-600 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Parsed: {owner}/{repo}#{prNumber}
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Owner
              </label>
              <input
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="ethereum"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Repository
              </label>
              <input
                type="text"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder="go-ethereum"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                PR Number
              </label>
              <input
                type="number"
                value={prNumber}
                onChange={(e) => setPrNumber(e.target.value ? parseInt(e.target.value) : '')}
                placeholder="123"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          </div>
        )}
        
        {/* Mode Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Analysis Mode
          </label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="quick"
                checked={mode === 'quick'}
                onChange={() => setMode('quick')}
                className="text-purple-600 focus:ring-purple-500"
              />
              <Zap className="w-4 h-4 text-yellow-500" />
              <span>Quick (~30s)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="deep"
                checked={mode === 'deep'}
                onChange={() => setMode('deep')}
                className="text-purple-600 focus:ring-purple-500"
              />
              <Search className="w-4 h-4 text-blue-500" />
              <span>Deep (~2-5min)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="both"
                checked={mode === 'both'}
                onChange={() => setMode('both')}
                className="text-purple-600 focus:ring-purple-500"
              />
              <RefreshCw className="w-4 h-4 text-purple-500" />
              <span>Both</span>
            </label>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {mode === 'quick' && 'Fast diff-based analysis. Good for initial feedback.'}
            {mode === 'deep' && 'Comprehensive graph-based analysis. Analyzes all entities.'}
            {mode === 'both' && 'Run quick first for immediate feedback, then deep for thorough analysis.'}
          </p>
        </div>
        
        {/* Optional GitHub Token */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            GitHub Token (optional)
          </label>
          <input
            type="password"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            placeholder="ghp_xxxx (for private repos)"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
          <p className="text-sm text-gray-500 mt-1">
            Required for private repositories. Uses server's token if not provided.
          </p>
        </div>
        
        {/* Analyze Button */}
        <div className="flex gap-3">
          <button
            onClick={handleAnalyze}
            disabled={loading || !owner || !repo || !prNumber}
            className="flex-1 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition"
          >
            {loading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                {jobStatus ? `${jobStatus.progress}% - ${jobStatus.message}` : 'Starting...'}
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Analyze PR
              </>
            )}
          </button>
          {loading && mode !== 'quick' && (
            <button
              onClick={handleCancelAnalysis}
              className="px-4 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
            >
              Cancel
            </button>
          )}
        </div>
        
        {/* Loading Progress Indicator */}
        {loading && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <Loader className="w-5 h-5 animate-spin text-blue-600" />
                <div>
                  <div className="font-medium text-blue-800">
                    {jobStatus?.message || 'Analysis in progress...'}
                  </div>
                  <div className="text-sm text-blue-600">
                    {mode === 'quick' && 'Quick analysis typically takes 30-60 seconds.'}
                    {mode === 'deep' && 'Deep analysis runs in background - you can wait or come back later.'}
                    {mode === 'both' && 'Running both analyses in background.'}
                  </div>
                </div>
              </div>
              {jobStatus && (
                <div className="text-2xl font-bold text-blue-700">{jobStatus.progress}%</div>
              )}
            </div>
            {/* Progress bar */}
            {jobStatus && (
              <div className="w-full bg-blue-200 rounded-full h-2 mt-3">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${jobStatus.progress}%` }}
                />
              </div>
            )}
            {jobId && (
              <div className="mt-2 text-xs text-blue-500">
                Job ID: {jobId}
              </div>
            )}
          </div>
        )}
        
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}
      </div>
      )}
      
      {/* Error (shown for both sources) */}
      {error && analysisSource === 'uploaded' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}
      
      {/* Results Section */}
      {result && (
        <div className="space-y-6">
          {/* Summary Card */}
          <div className={`rounded-lg shadow p-6 ${
            result.compliance_passed 
              ? 'bg-green-50 border border-green-200' 
              : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {result.compliance_passed ? (
                  <CheckCircle className="w-8 h-8 text-green-600" />
                ) : (
                  <XCircle className="w-8 h-8 text-red-600" />
                )}
                <div>
                  <h3 className="text-xl font-bold">
                    {result.compliance_passed ? 'Compliance Check Passed' : 'Compliance Check Failed'}
                  </h3>
                  <p className="text-gray-600">{result.pr}</p>
                  {result.commit_sha && (
                    <p className="text-sm text-gray-500 mt-1">
                      Commit: <code className="bg-gray-200 px-1 rounded">{result.commit_sha.substring(0, 8)}</code>
                    </p>
                  )}
                </div>
              </div>
              <a
                href={`https://github.com/${owner}/${repo}/pull/${prNumber}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-purple-600 hover:text-purple-800"
              >
                View PR <ExternalLink className="w-4 h-4" />
              </a>
            </div>
            
            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 mt-6">
              <div className="bg-white rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-red-600">{result.total_critical}</div>
                <div className="text-sm text-gray-600">Critical</div>
              </div>
              <div className="bg-white rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-yellow-600">{result.total_warning}</div>
                <div className="text-sm text-gray-600">Warnings</div>
              </div>
              <div className="bg-white rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-blue-600">
                  {result.combined_deviations.length - result.total_critical - result.total_warning}
                </div>
                <div className="text-sm text-gray-600">Info</div>
              </div>
              <div className="bg-white rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-gray-600">
                  {result.combined_deviations.length}
                </div>
                <div className="text-sm text-gray-600">Total</div>
              </div>
            </div>
            
            {/* Commits Included Note */}
            {(result.quick?.commits || result.deep?.commits) && (
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <GitBranch className="w-4 h-4 text-blue-600 mt-0.5" />
                  <div className="text-sm">
                    <span className="font-medium text-blue-800">
                      {result.quick?.analysis_note || result.deep?.analysis_note || 
                       `Analysis covers ${result.quick?.total_commits || result.deep?.total_commits || 1} commit(s)`}
                    </span>
                    {((result.quick?.commits?.length || 0) > 0 || (result.deep?.commits?.length || 0) > 0) && (
                      <div className="mt-2 space-y-1">
                        {(result.quick?.commits || result.deep?.commits || []).map((commit, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-xs text-blue-700">
                            <code className="bg-blue-100 px-1.5 py-0.5 rounded">{commit.sha}</code>
                            <span className="truncate">{commit.message}</span>
                            <span className="text-blue-500 flex-shrink-0">by {commit.author}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* Analysis Details */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Analysis Details</h3>
            
            <div className="grid grid-cols-2 gap-4">
              {/* Quick Analysis */}
              {result.quick && (
                <div className="border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Zap className="w-5 h-5 text-yellow-500" />
                    <span className="font-medium">Quick Analysis</span>
                    {result.quick.success ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                  </div>
                  {result.quick.error ? (
                    <div className="text-sm text-amber-600 bg-amber-50 p-2 rounded">
                      {result.quick.error}
                    </div>
                  ) : (
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Duration:</span>
                        <span className="font-medium">{result.quick.duration_seconds.toFixed(1)}s</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Files:</span>
                        <span className="font-medium">{result.quick.files_analyzed}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Issues:</span>
                        <span className="font-medium">{result.quick.deviations?.length || 0}</span>
                      </div>
                      {result.quick.total_commits && result.quick.total_commits > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Commits:</span>
                          <span className="font-medium">{result.quick.total_commits}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              
              {/* Deep Analysis */}
              {result.deep && (
                <div className="border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Search className="w-5 h-5 text-blue-500" />
                    <span className="font-medium">Deep Analysis</span>
                    {result.deep.success ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                  </div>
                  {result.deep.error ? (
                    <div className="text-sm text-red-600">{result.deep.error}</div>
                  ) : (
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Duration:</span>
                        <span className="font-medium">{result.deep.duration_seconds.toFixed(1)}s</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Files:</span>
                        <span className="font-medium">{result.deep.files_analyzed}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Entities:</span>
                        <span className="font-medium">{result.deep.entities_analyzed}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Issues:</span>
                        <span className="font-medium">{result.deep.deviations?.length || 0}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          
          {/* Graph Statistics (Deep Analysis Only) */}
          {result.deep?.graph_stats && (
            <GraphStatsCard 
              stats={result.deep.graph_stats} 
              graphId={result.graph_id}
              graphPersisted={result.deep.graph_persisted}
            />
          )}
          
          {/* Deviations List */}
          {result.combined_deviations.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">
                Issues Found ({result.combined_deviations.length})
              </h3>
              
              <div className="space-y-3">
                {result.combined_deviations.map((dev: Deviation, index: number) => (
                  <div 
                    key={index}
                    className="border rounded-lg overflow-hidden"
                  >
                    <button
                      onClick={() => toggleDeviation(index)}
                      className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition"
                    >
                      <div className="flex items-center gap-3">
                        {getSeverityIcon(dev.severity)}
                        <span className={`px-2 py-1 text-xs rounded border ${getSeverityBadge(dev.severity)}`}>
                          {dev.severity?.toUpperCase()}
                        </span>
                        <span className="font-medium text-gray-900">
                          {dev.rule_id || 'Compliance Issue'}
                        </span>
                      </div>
                      {expandedDeviations.has(index) ? (
                        <ChevronUp className="w-5 h-5 text-gray-500" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-500" />
                      )}
                    </button>
                    
                    {expandedDeviations.has(index) && (
                      <div className="px-4 py-3 border-t bg-white space-y-3">
                        <div>
                          <div className="text-sm font-medium text-gray-700">Description</div>
                          <div className="text-gray-600">{dev.description}</div>
                        </div>
                        
                        {/* Location with file, line, and commit */}
                        {(dev.file || dev.code_location) && (
                          <div>
                            <div className="text-sm font-medium text-gray-700">Location</div>
                            <div className="flex flex-wrap items-center gap-2">
                              <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                                {dev.file || dev.code_location?.split(':')[0]}
                                {dev.line ? `:${dev.line}` : (dev.code_location?.includes(':') ? `:${dev.code_location.split(':')[1]}` : '')}
                              </code>
                              {(dev.commit_sha || result.commit_sha) && (
                                <span className="text-xs text-gray-500">
                                  @ <code className="bg-gray-100 px-1 rounded">{(dev.commit_sha || result.commit_sha)?.substring(0, 7)}</code>
                                </span>
                              )}
                              {/* Link to GitHub if we have file and line */}
                              {dev.file && dev.line && (
                                <a
                                  href={`https://github.com/${owner}/${repo}/blob/${result.commit_sha || 'HEAD'}/${dev.file}#L${dev.line}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-purple-600 hover:text-purple-800 flex items-center gap-1"
                                >
                                  <ExternalLink className="w-3 h-3" />
                                  View on GitHub
                                </a>
                              )}
                            </div>
                          </div>
                        )}
                        
                        {/* Entity name if available */}
                        {dev.entity_name && (
                          <div>
                            <div className="text-sm font-medium text-gray-700">Entity</div>
                            <code className="text-sm bg-gray-100 px-2 py-1 rounded">{dev.entity_name}</code>
                          </div>
                        )}
                        
                        {dev.spec_reference && (
                          <div>
                            <div className="text-sm font-medium text-gray-700">Specification</div>
                            <div className="text-gray-600">{dev.spec_reference}</div>
                          </div>
                        )}
                        
                        {dev.recommendation && (
                          <div>
                            <div className="text-sm font-medium text-gray-700">Recommendation</div>
                            <div className="text-gray-600">{dev.recommendation}</div>
                          </div>
                        )}
                        
                        {dev.explanation && (
                          <div>
                            <div className="text-sm font-medium text-gray-700">Explanation</div>
                            <div className="text-gray-600 text-sm">{dev.explanation}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* No Issues */}
          {result.combined_deviations.length === 0 && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
              <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-green-800">No Issues Found!</h3>
              <p className="text-green-700 mt-2">
                This PR appears to comply with Ethereum protocol specifications.
              </p>
            </div>
          )}
        </div>
      )}
      
      {/* Help Section */}
      {!result && !loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="font-semibold text-blue-800 mb-2">How to Test</h3>
          <ol className="list-decimal list-inside space-y-2 text-blue-700">
            <li>Paste a GitHub PR URL or enter owner/repo/PR number manually</li>
            <li>Select an analysis mode:
              <ul className="list-disc list-inside ml-6 mt-1 text-sm">
                <li><strong>Quick:</strong> Fast diff-based analysis (~30 seconds)</li>
                <li><strong>Deep:</strong> Clones repo, builds graph, analyzes entities (~2-5 min)</li>
                <li><strong>Both:</strong> Runs quick first for fast feedback, then deep for thoroughness</li>
              </ul>
            </li>
            <li>Click "Analyze PR" to start the analysis</li>
            <li>View the compliance results and any deviations found</li>
          </ol>
          
          <div className="mt-4 p-4 bg-white rounded-lg">
            <div className="text-sm font-medium text-gray-700 mb-2">Example PRs to try:</div>
            <div className="space-y-1 text-sm">
              <code className="block text-gray-600">https://github.com/ethereum/go-ethereum/pull/28000</code>
              <code className="block text-gray-600">https://github.com/ethereum/execution-specs/pull/100</code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
