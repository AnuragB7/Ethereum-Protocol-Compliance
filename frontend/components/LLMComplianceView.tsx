'use client';

import React, { useState, useEffect } from 'react';
import { 
  Download, 
  Play, 
  RefreshCw, 
  Search, 
  AlertTriangle, 
  CheckCircle,
  XCircle,
  Info,
  Loader,
  GitBranch,
  Database,
  Zap
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  cloneSpecs,
  ingestSpecs,
  getSpecStats,
  querySpecs,
  runLLMCompliance,
  resetSpecs,
  getAvailableForks,
} from '../lib/api';

interface SpecStats {
  indexed: boolean;
  total_files?: number;
  total_chunks?: number;
  forks?: string[];
  eips?: string[];
}

interface Deviation {
  rule_id: string;
  spec_reference: string;
  spec_fork: string;
  spec_file: string;
  severity: string;
  category: string;
  description: string;
  explanation: string;
  recommendation: string;
  code_location: string;
  entity_name: string;
  confidence: number;
  eip_references: string[];
}

interface ComplianceReport {
  timestamp: string;
  total_entities_analyzed: number;
  total_specs_checked: number;
  total_deviations: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  compliance_score: number;
  deviations: Deviation[];
  entities_analyzed: string[];
}

export default function LLMComplianceView() {
  // State
  const [activeTab, setActiveTab] = useState<'setup' | 'query' | 'compliance'>('setup');
  const [specStats, setSpecStats] = useState<SpecStats | null>(null);
  const [availableForks, setAvailableForks] = useState<string[]>([]);
  const [selectedForks, setSelectedForks] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Query state
  const [queryText, setQueryText] = useState('');
  const [queryResults, setQueryResults] = useState<any[]>([]);
  const [queryAlpha, setQueryAlpha] = useState(0.5);
  
  // Compliance state
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null);
  const [maxEntities, setMaxEntities] = useState(20);
  
  useEffect(() => {
    loadSpecStats();
    loadAvailableForks();
  }, []);
  
  const loadSpecStats = async () => {
    try {
      const response = await getSpecStats();
      setSpecStats(response.stats);
    } catch (err: any) {
      console.error('Failed to load spec stats:', err);
    }
  };
  
  const loadAvailableForks = async () => {
    try {
      const response = await getAvailableForks();
      setAvailableForks(response.forks || []);
      // Default to recent forks
      if (response.recent_forks) {
        setSelectedForks(response.recent_forks.filter((f: string) => response.forks?.includes(f)));
      }
    } catch (err: any) {
      console.error('Failed to load forks:', err);
    }
  };
  
  const handleCloneSpecs = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      // Use forks/amsterdam - the current default branch of execution-specs
      const result = await cloneSpecs('forks/amsterdam', false);
      setSuccess(result.message);
      loadAvailableForks();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to clone specs');
    } finally {
      setLoading(false);
    }
  };
  
  const handleIngestSpecs = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const forksToIngest = selectedForks.length > 0 ? selectedForks : undefined;
      const result = await ingestSpecs(forksToIngest, true);
      setSuccess(`Ingested ${result.stats.total_chunks} spec chunks from ${result.stats.forks_ingested.join(', ')}`);
      loadSpecStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to ingest specs');
    } finally {
      setLoading(false);
    }
  };
  
  const handleResetSpecs = async () => {
    if (!confirm('Are you sure you want to reset the specification index?')) return;
    
    setLoading(true);
    setError('');
    
    try {
      await resetSpecs();
      setSuccess('Specification index reset successfully');
      setSpecStats(null);
      setComplianceReport(null);
      loadSpecStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset specs');
    } finally {
      setLoading(false);
    }
  };
  
  const handleQuerySpecs = async () => {
    if (!queryText.trim()) return;
    
    setLoading(true);
    setError('');
    
    try {
      const result = await querySpecs(queryText, 5, queryAlpha);
      setQueryResults(result.results || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Query failed');
    } finally {
      setLoading(false);
    }
  };
  
  const handleRunCompliance = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const result = await runLLMCompliance(maxEntities, 5);
      setComplianceReport(result.report);
      setSuccess(`Compliance check complete! Score: ${result.report.compliance_score}%`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Compliance check failed');
    } finally {
      setLoading(false);
    }
  };
  
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <XCircle className="text-red-500" size={20} />;
      case 'warning':
        return <AlertTriangle className="text-yellow-500" size={20} />;
      default:
        return <Info className="text-blue-500" size={20} />;
    }
  };
  
  const getSeverityBadge = (severity: string) => {
    const colors = {
      critical: 'bg-red-100 text-red-800 border-red-200',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      info: 'bg-blue-100 text-blue-800 border-blue-200',
    };
    return colors[severity as keyof typeof colors] || colors.info;
  };
  
  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold text-gray-800">LLM Compliance Check</h2>
          <p className="text-gray-600 mt-1">
            Semantic compliance checking against Ethereum execution specifications
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Zap className="text-purple-500" size={24} />
          <span className="text-sm text-gray-500">Powered by Qdrant Hybrid Search</span>
        </div>
      </div>
      
      {/* Tab Navigation */}
      <div className="flex gap-4 mb-6 border-b">
        <button
          onClick={() => setActiveTab('setup')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'setup'
              ? 'text-primary-600 border-b-2 border-primary-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Database className="inline mr-2" size={18} />
          Setup Specs
        </button>
        <button
          onClick={() => setActiveTab('query')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'query'
              ? 'text-primary-600 border-b-2 border-primary-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Search className="inline mr-2" size={18} />
          Query Specs
        </button>
        <button
          onClick={() => setActiveTab('compliance')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'compliance'
              ? 'text-primary-600 border-b-2 border-primary-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <CheckCircle className="inline mr-2" size={18} />
          Run Compliance
        </button>
      </div>
      
      {/* Error/Success Messages */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <XCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />
          <p className="text-red-700">{error}</p>
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-2">
          <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
          <p className="text-green-700">{success}</p>
        </div>
      )}
      
      {/* Setup Tab */}
      {activeTab === 'setup' && (
        <div className="space-y-6">
          {/* Current Status */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Specification Index Status</h3>
            
            {specStats?.indexed ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-green-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Status</p>
                  <p className="text-xl font-bold text-green-600">Indexed</p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Spec Chunks</p>
                  <p className="text-xl font-bold text-blue-600">{specStats.total_chunks}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Forks</p>
                  <p className="text-xl font-bold text-purple-600">{specStats.forks?.length || 0}</p>
                </div>
                <div className="bg-orange-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">EIPs Found</p>
                  <p className="text-xl font-bold text-orange-600">{specStats.eips?.length || 0}</p>
                </div>
              </div>
            ) : (
              <div className="bg-yellow-50 p-4 rounded-lg">
                <p className="text-yellow-700">
                  Specifications not indexed. Follow the steps below to set up.
                </p>
              </div>
            )}
            
            {specStats?.indexed && specStats.forks && (
              <div className="mt-4">
                <p className="text-sm text-gray-600 mb-2">Indexed Forks:</p>
                <div className="flex flex-wrap gap-2">
                  {specStats.forks.map((fork) => (
                    <span key={fork} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                      {fork}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Step 1: Clone Specs */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">
                1
              </div>
              <h3 className="text-lg font-bold text-gray-800">Clone Ethereum Execution Specs</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Clone the official <code className="bg-gray-100 px-1 rounded">ethereum/execution-specs</code> repository 
              from GitHub. This contains the Python specifications for all Ethereum forks.
            </p>
            
            <button
              onClick={handleCloneSpecs}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400"
            >
              {loading ? <Loader className="animate-spin" size={18} /> : <Download size={18} />}
              Clone from GitHub
            </button>
          </div>
          
          {/* Step 2: Select Forks */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">
                2
              </div>
              <h3 className="text-lg font-bold text-gray-800">Select Forks to Index</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Choose which Ethereum forks to index. Recent forks (Prague, Cancun) are recommended.
            </p>
            
            {availableForks.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {availableForks.map((fork) => (
                  <button
                    key={fork}
                    onClick={() => {
                      setSelectedForks((prev) =>
                        prev.includes(fork)
                          ? prev.filter((f) => f !== fork)
                          : [...prev, fork]
                      );
                    }}
                    className={`px-3 py-1 rounded-full text-sm border transition ${
                      selectedForks.includes(fork)
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:border-primary-400'
                    }`}
                  >
                    {fork}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">Clone specs first to see available forks</p>
            )}
          </div>
          
          {/* Step 3: Ingest */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">
                3
              </div>
              <h3 className="text-lg font-bold text-gray-800">Ingest into Qdrant (Hybrid Search)</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Parse specifications and create embeddings for hybrid search (semantic + keyword).
              This enables both conceptual matching and exact EIP/function name lookup.
            </p>
            
            <div className="flex gap-4">
              <button
                onClick={handleIngestSpecs}
                disabled={loading || availableForks.length === 0}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:bg-gray-400"
              >
                {loading ? <Loader className="animate-spin" size={18} /> : <Play size={18} />}
                Ingest Specifications
              </button>
              
              <button
                onClick={handleResetSpecs}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition"
              >
                <RefreshCw size={18} />
                Reset Index
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Query Tab */}
      {activeTab === 'query' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Query Specifications</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Search Query
                </label>
                <input
                  type="text"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleQuerySpecs()}
                  placeholder="e.g., 'EIP-1559 gas calculation' or 'transaction nonce validation'"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Search Balance (Alpha): {queryAlpha.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={queryAlpha}
                  onChange={(e) => setQueryAlpha(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Keyword (BM25)</span>
                  <span>Semantic (Embedding)</span>
                </div>
              </div>
              
              <button
                onClick={handleQuerySpecs}
                disabled={loading || !queryText.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400"
              >
                {loading ? <Loader className="animate-spin" size={18} /> : <Search size={18} />}
                Search
              </button>
            </div>
          </div>
          
          {/* Query Results */}
          {queryResults.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow-lg">
              <h3 className="text-lg font-bold mb-4 text-gray-800">
                Results ({queryResults.length})
              </h3>
              
              <div className="space-y-4">
                {queryResults.map((result, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-sm">
                          {result.fork}
                        </span>
                        <span className="text-gray-600 text-sm">{result.name}</span>
                      </div>
                      <span className="text-sm text-gray-500">
                        Score: {result.score?.toFixed(3)}
                      </span>
                    </div>
                    
                    <p className="text-xs text-gray-500 mb-2">{result.file_path}</p>
                    
                    {result.eip_references && (
                      <div className="flex gap-1 mb-2">
                        {result.eip_references.split(',').filter(Boolean).map((eip: string) => (
                          <span key={eip} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {eip.trim()}
                          </span>
                        ))}
                      </div>
                    )}
                    
                    <pre className="text-sm bg-gray-50 p-3 rounded overflow-x-auto">
                      {result.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Compliance Tab */}
      {activeTab === 'compliance' && (
        <div className="space-y-6">
          {/* Run Compliance */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Run LLM Compliance Check</h3>
            
            <p className="text-gray-600 mb-4">
              Analyze your indexed codebase against Ethereum specifications using LLM-powered semantic analysis.
              Each code entity is compared against relevant specs retrieved via hybrid search.
            </p>
            
            <div className="flex items-center gap-4 mb-4">
              <label className="text-sm font-medium text-gray-700">
                Max Entities to Analyze:
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={maxEntities}
                onChange={(e) => setMaxEntities(parseInt(e.target.value) || 20)}
                className="w-24 px-3 py-2 border border-gray-300 rounded-lg"
              />
              <span className="text-xs text-gray-500">
                (Higher = more comprehensive but slower/costlier)
              </span>
            </div>
            
            <button
              onClick={handleRunCompliance}
              disabled={loading || !specStats?.indexed}
              className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:bg-gray-400"
            >
              {loading ? <Loader className="animate-spin" size={18} /> : <Play size={18} />}
              Run Compliance Check
            </button>
            
            {!specStats?.indexed && (
              <p className="mt-2 text-sm text-yellow-600">
                Please ingest specifications first (Setup Specs tab)
              </p>
            )}
          </div>
          
          {/* Compliance Report */}
          {complianceReport && (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="bg-white p-4 rounded-lg shadow">
                  <p className="text-sm text-gray-600">Compliance Score</p>
                  <p className={`text-3xl font-bold ${
                    complianceReport.compliance_score >= 80 ? 'text-green-600' :
                    complianceReport.compliance_score >= 50 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {complianceReport.compliance_score}%
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg shadow">
                  <p className="text-sm text-gray-600">Entities Analyzed</p>
                  <p className="text-3xl font-bold text-blue-600">
                    {complianceReport.total_entities_analyzed}
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg shadow">
                  <p className="text-sm text-gray-600">Critical Issues</p>
                  <p className="text-3xl font-bold text-red-600">
                    {complianceReport.critical_count}
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg shadow">
                  <p className="text-sm text-gray-600">Warnings</p>
                  <p className="text-3xl font-bold text-yellow-600">
                    {complianceReport.warning_count}
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg shadow">
                  <p className="text-sm text-gray-600">Info</p>
                  <p className="text-3xl font-bold text-blue-600">
                    {complianceReport.info_count}
                  </p>
                </div>
              </div>
              
              {/* Deviations List */}
              <div className="bg-white p-6 rounded-lg shadow-lg">
                <h3 className="text-xl font-bold mb-4 text-gray-800">
                  Deviations ({complianceReport.total_deviations})
                </h3>
                
                {complianceReport.deviations.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <CheckCircle className="mx-auto mb-2 text-green-500" size={48} />
                    <p>No deviations found! Your code appears to comply with the specifications.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {complianceReport.deviations.map((deviation, idx) => (
                      <div 
                        key={idx} 
                        className={`border rounded-lg p-4 ${
                          deviation.severity === 'critical' ? 'border-red-300 bg-red-50' :
                          deviation.severity === 'warning' ? 'border-yellow-300 bg-yellow-50' :
                          'border-blue-300 bg-blue-50'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2">
                            {getSeverityIcon(deviation.severity)}
                            <span className={`px-2 py-1 rounded text-xs font-medium border ${getSeverityBadge(deviation.severity)}`}>
                              {deviation.severity.toUpperCase()}
                            </span>
                            <span className="text-gray-600 font-medium">{deviation.entity_name}</span>
                          </div>
                          <span className="text-xs text-gray-500">
                            Confidence: {(deviation.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        
                        <div className="mb-3">
                          <p className="text-sm text-gray-500 mb-1">Spec Reference:</p>
                          <p className="font-medium">{deviation.spec_reference}</p>
                          <p className="text-xs text-gray-500">
                            {deviation.spec_fork}/{deviation.spec_file}
                          </p>
                        </div>
                        
                        {deviation.eip_references?.length > 0 && (
                          <div className="flex gap-1 mb-3">
                            {deviation.eip_references.map((eip) => (
                              <span key={eip} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                                {eip}
                              </span>
                            ))}
                          </div>
                        )}
                        
                        <div className="space-y-2 text-sm">
                          <div>
                            <p className="font-medium text-gray-700">Description:</p>
                            <p className="text-gray-600">{deviation.description}</p>
                          </div>
                          
                          <div>
                            <p className="font-medium text-gray-700">Explanation:</p>
                            <p className="text-gray-600">{deviation.explanation}</p>
                          </div>
                          
                          <div>
                            <p className="font-medium text-gray-700">Recommendation:</p>
                            <p className="text-gray-600">{deviation.recommendation}</p>
                          </div>
                          
                          <div className="text-xs text-gray-500">
                            Code Location: {deviation.code_location}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
