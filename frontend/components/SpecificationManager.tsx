'use client';

import React, { useEffect, useState } from 'react';
import { 
  listSpecifications, 
  fetchEIP, 
  searchEIPs, 
  uploadSpecification,
  addCustomRule,
  getComplianceRules,
  cloneSpecs,
  ingestSpecs,
  getSpecStats,
  querySpecs,
  resetSpecs,
  getAvailableForks,
} from '../lib/api';
import { 
  Book, 
  Plus, 
  Upload, 
  Search, 
  Download,
  Trash2,
  Settings,
  Check,
  X,
  FileText,
  Shield,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronRight,
  Database,
  Play,
  RefreshCw,
  Loader,
  CheckCircle,
  XCircle,
  Zap
} from 'lucide-react';

interface Rule {
  id: string;
  source: string;
  category: string;
  severity: string;
  description: string;
  patterns: string[];
  must_contain: string[];
  must_not_contain: string[];
  recommendation: string;
  languages: string[];
}

interface SpecSummary {
  loaded_specs: string[];
  total_rules: number;
  rules_by_source: Record<string, number>;
  rules_by_severity: Record<string, number>;
  rules_by_category: Record<string, number>;
}

interface EIPSearchResult {
  number: number;
  title: string;
  cached: boolean;
}

interface QdrantSpecStats {
  indexed: boolean;
  total_files?: number;
  total_chunks?: number;
  forks?: string[];
  eips?: string[];
}

export default function SpecificationManager() {
  const [specs, setSpecs] = useState<SpecSummary | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EIPSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeTab, setActiveTab] = useState<'qdrant-index' | 'overview' | 'rules' | 'add-eip' | 'custom-rule' | 'query-specs'>('qdrant-index');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);
  const [filterSource, setFilterSource] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  
  // Qdrant Spec Index state
  const [qdrantSpecStats, setQdrantSpecStats] = useState<QdrantSpecStats | null>(null);
  const [availableForks, setAvailableForks] = useState<string[]>([]);
  const [selectedForks, setSelectedForks] = useState<string[]>([]);
  const [specLoading, setSpecLoading] = useState(false);
  const [specError, setSpecError] = useState('');
  const [specSuccess, setSpecSuccess] = useState('');
  
  // Query specs state
  const [queryText, setQueryText] = useState('');
  const [queryResults, setQueryResults] = useState<any[]>([]);
  const [queryAlpha, setQueryAlpha] = useState(0.5);
  
  // Custom rule form
  const [customRule, setCustomRule] = useState({
    id: '',
    source: 'custom',
    category: 'general',
    severity: 'warning',
    description: '',
    patterns: '',
    must_contain: '',
    must_not_contain: '',
    recommendation: '',
    languages: 'solidity,go,javascript,typescript'
  });
  
  // File upload
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadSpecifications();
    loadQdrantSpecStats();
    loadAvailableForks();
  }, []);
  
  const loadQdrantSpecStats = async () => {
    try {
      const response = await getSpecStats();
      setQdrantSpecStats(response.stats);
    } catch (err: any) {
      console.error('Failed to load Qdrant spec stats:', err);
    }
  };
  
  const loadAvailableForks = async () => {
    try {
      const response = await getAvailableForks();
      setAvailableForks(response.forks || []);
      if (response.recent_forks) {
        setSelectedForks(response.recent_forks.filter((f: string) => response.forks?.includes(f)));
      }
    } catch (err: any) {
      console.error('Failed to load forks:', err);
    }
  };
  
  const handleCloneSpecs = async () => {
    setSpecLoading(true);
    setSpecError('');
    setSpecSuccess('');
    
    try {
      const result = await cloneSpecs('forks/amsterdam', false);
      setSpecSuccess(result.message);
      loadAvailableForks();
    } catch (err: any) {
      setSpecError(err.response?.data?.detail || 'Failed to clone specs');
    } finally {
      setSpecLoading(false);
    }
  };
  
  const handleIngestSpecs = async () => {
    setSpecLoading(true);
    setSpecError('');
    setSpecSuccess('');
    
    try {
      const forksToIngest = selectedForks.length > 0 ? selectedForks : undefined;
      const result = await ingestSpecs(forksToIngest, true);
      setSpecSuccess(`Ingested ${result.stats.total_chunks} spec chunks from ${result.stats.forks_ingested.join(', ')}`);
      loadQdrantSpecStats();
    } catch (err: any) {
      setSpecError(err.response?.data?.detail || 'Failed to ingest specs');
    } finally {
      setSpecLoading(false);
    }
  };
  
  const handleResetSpecs = async () => {
    if (!confirm('Are you sure you want to reset the specification index?')) return;
    
    setSpecLoading(true);
    setSpecError('');
    
    try {
      await resetSpecs();
      setSpecSuccess('Specification index reset successfully');
      setQdrantSpecStats(null);
      loadQdrantSpecStats();
    } catch (err: any) {
      setSpecError(err.response?.data?.detail || 'Failed to reset specs');
    } finally {
      setSpecLoading(false);
    }
  };
  
  const handleQuerySpecs = async () => {
    if (!queryText.trim()) return;
    
    setSpecLoading(true);
    setSpecError('');
    
    try {
      const result = await querySpecs(queryText, 5, queryAlpha);
      setQueryResults(result.results || []);
    } catch (err: any) {
      setSpecError(err.response?.data?.detail || 'Query failed');
    } finally {
      setSpecLoading(false);
    }
  };

  const loadSpecifications = async () => {
    try {
      setLoading(true);
      const [specsData, rulesData] = await Promise.all([
        listSpecifications(),
        getComplianceRules()
      ]);
      setSpecs(specsData);
      setRules(rulesData.rules || []);
    } catch (error) {
      console.error('Failed to load specifications:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setSearching(true);
    try {
      const results = await searchEIPs(searchQuery);
      setSearchResults(results.results || []);
    } catch (error) {
      console.error('Failed to search EIPs:', error);
    } finally {
      setSearching(false);
    }
  };

  const handleLoadEIP = async (eipNumber: number) => {
    try {
      await fetchEIP(eipNumber, true);
      await loadSpecifications();
      alert(`EIP-${eipNumber} loaded successfully!`);
    } catch (error) {
      console.error('Failed to load EIP:', error);
      alert(`Failed to load EIP-${eipNumber}`);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    try {
      await uploadSpecification(file);
      await loadSpecifications();
      alert('Specification uploaded successfully!');
    } catch (error) {
      console.error('Failed to upload specification:', error);
      alert('Failed to upload specification');
    } finally {
      setUploading(false);
    }
  };

  const handleAddCustomRule = async () => {
    if (!customRule.id || !customRule.description) {
      alert('Rule ID and description are required');
      return;
    }
    
    try {
      await addCustomRule({
        id: customRule.id,
        source: customRule.source,
        category: customRule.category,
        severity: customRule.severity,
        description: customRule.description,
        patterns: customRule.patterns.split(',').map(s => s.trim()).filter(Boolean),
        must_contain: customRule.must_contain.split(',').map(s => s.trim()).filter(Boolean),
        must_not_contain: customRule.must_not_contain.split(',').map(s => s.trim()).filter(Boolean),
        recommendation: customRule.recommendation,
        languages: customRule.languages.split(',').map(s => s.trim()).filter(Boolean)
      });
      
      await loadSpecifications();
      setCustomRule({
        id: '',
        source: 'custom',
        category: 'general',
        severity: 'warning',
        description: '',
        patterns: '',
        must_contain: '',
        must_not_contain: '',
        recommendation: '',
        languages: 'solidity,go,javascript,typescript'
      });
      alert('Custom rule added successfully!');
      setActiveTab('rules');
    } catch (error) {
      console.error('Failed to add custom rule:', error);
      alert('Failed to add custom rule');
    }
  };

  const filteredRules = rules.filter(rule => {
    if (filterSource && rule.source !== filterSource) return false;
    if (filterSeverity && rule.severity !== filterSeverity) return false;
    return true;
  });

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="text-red-500" size={16} />;
      case 'warning':
        return <AlertTriangle className="text-yellow-500" size={16} />;
      default:
        return <Info className="text-blue-500" size={16} />;
    }
  };

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-blue-100 text-blue-800';
    }
  };

  const popularEIPs = [
    { number: 20, title: 'ERC-20 Token Standard' },
    { number: 721, title: 'ERC-721 NFT Standard' },
    { number: 1155, title: 'ERC-1155 Multi Token' },
    { number: 2612, title: 'ERC-2612 Permit' },
    { number: 4626, title: 'ERC-4626 Tokenized Vault' },
    { number: 165, title: 'ERC-165 Interface Detection' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold text-gray-800">Specification Manager</h2>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 cursor-pointer transition-colors">
            <Upload size={18} />
            Upload Spec
            <input
              type="file"
              accept=".yaml,.yml,.json"
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-6 overflow-x-auto">
        <button
          onClick={() => setActiveTab('qdrant-index')}
          className={`px-6 py-3 font-medium flex items-center gap-2 whitespace-nowrap ${activeTab === 'qdrant-index' ? 'border-b-2 border-purple-600 text-purple-600' : 'text-gray-500'}`}
        >
          <Database size={18} />
          Qdrant Index
        </button>
        <button
          onClick={() => setActiveTab('query-specs')}
          className={`px-6 py-3 font-medium flex items-center gap-2 whitespace-nowrap ${activeTab === 'query-specs' ? 'border-b-2 border-purple-600 text-purple-600' : 'text-gray-500'}`}
        >
          <Search size={18} />
          Query Specs
        </button>
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-6 py-3 font-medium whitespace-nowrap ${activeTab === 'overview' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          EIP Rules
        </button>
        <button
          onClick={() => setActiveTab('rules')}
          className={`px-6 py-3 font-medium whitespace-nowrap ${activeTab === 'rules' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Rules ({rules.length})
        </button>
        <button
          onClick={() => setActiveTab('add-eip')}
          className={`px-6 py-3 font-medium whitespace-nowrap ${activeTab === 'add-eip' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Add EIP
        </button>
        <button
          onClick={() => setActiveTab('custom-rule')}
          className={`px-6 py-3 font-medium whitespace-nowrap ${activeTab === 'custom-rule' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Custom Rule
        </button>
      </div>
      
      {/* Qdrant Index Tab */}
      {activeTab === 'qdrant-index' && (
        <div className="space-y-6">
          {/* Status Messages */}
          {specError && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <XCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />
              <p className="text-red-700">{specError}</p>
            </div>
          )}
          
          {specSuccess && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-2">
              <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
              <p className="text-green-700">{specSuccess}</p>
            </div>
          )}
          
          {/* Current Status */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="text-purple-500" size={24} />
              <h3 className="text-xl font-bold text-gray-800">Ethereum Specification Index (Qdrant)</h3>
            </div>
            <p className="text-gray-600 mb-4">
              Hybrid search index for Ethereum execution specifications. Required for LLM compliance analysis.
            </p>
            
            {qdrantSpecStats?.indexed ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-green-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Status</p>
                  <p className="text-xl font-bold text-green-600">Indexed</p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Spec Chunks</p>
                  <p className="text-xl font-bold text-blue-600">{qdrantSpecStats.total_chunks}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Forks</p>
                  <p className="text-xl font-bold text-purple-600">{qdrantSpecStats.forks?.length || 0}</p>
                </div>
                <div className="bg-orange-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">EIPs Found</p>
                  <p className="text-xl font-bold text-orange-600">{qdrantSpecStats.eips?.length || 0}</p>
                </div>
              </div>
            ) : (
              <div className="bg-yellow-50 p-4 rounded-lg">
                <p className="text-yellow-700">
                  Specifications not indexed. Follow the steps below to set up.
                </p>
              </div>
            )}
            
            {qdrantSpecStats?.indexed && qdrantSpecStats.forks && (
              <div className="mt-4">
                <p className="text-sm text-gray-600 mb-2">Indexed Forks:</p>
                <div className="flex flex-wrap gap-2">
                  {qdrantSpecStats.forks.map((fork) => (
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
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">1</div>
              <h3 className="text-lg font-bold text-gray-800">Clone Ethereum Execution Specs</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Clone the official <code className="bg-gray-100 px-1 rounded">ethereum/execution-specs</code> repository 
              from GitHub. This contains the Python specifications for all Ethereum forks.
            </p>
            
            <button
              onClick={handleCloneSpecs}
              disabled={specLoading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400"
            >
              {specLoading ? <Loader className="animate-spin" size={18} /> : <Download size={18} />}
              Clone from GitHub
            </button>
          </div>
          
          {/* Step 2: Select Forks */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">2</div>
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
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 font-bold">3</div>
              <h3 className="text-lg font-bold text-gray-800">Ingest into Qdrant (Hybrid Search)</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Parse specifications and create embeddings for hybrid search (semantic + keyword).
              This enables both conceptual matching and exact EIP/function name lookup.
            </p>
            
            <div className="flex gap-4">
              <button
                onClick={handleIngestSpecs}
                disabled={specLoading || availableForks.length === 0}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:bg-gray-400"
              >
                {specLoading ? <Loader className="animate-spin" size={18} /> : <Play size={18} />}
                Ingest Specifications
              </button>
              
              <button
                onClick={handleResetSpecs}
                disabled={specLoading}
                className="flex items-center gap-2 px-4 py-2 text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition"
              >
                <RefreshCw size={18} />
                Reset Index
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Query Specs Tab */}
      {activeTab === 'query-specs' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Query Ethereum Specifications</h3>
            
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
                disabled={specLoading || !queryText.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400"
              >
                {specLoading ? <Loader className="animate-spin" size={18} /> : <Search size={18} />}
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

      {activeTab === 'overview' && specs && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-gray-600 text-sm font-medium">Loaded Specifications</h3>
                <Book className="text-primary-600" size={24} />
              </div>
              <p className="text-3xl font-bold text-gray-800">{specs.loaded_specs.length}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {specs.loaded_specs.map(spec => (
                  <span key={spec} className="px-2 py-0.5 bg-gray-100 rounded text-xs">{spec}</span>
                ))}
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-gray-600 text-sm font-medium">Total Rules</h3>
                <Shield className="text-green-600" size={24} />
              </div>
              <p className="text-3xl font-bold text-gray-800">{specs.total_rules}</p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-gray-600 text-sm font-medium">By Severity</h3>
                <AlertTriangle className="text-yellow-600" size={24} />
              </div>
              <div className="space-y-1 mt-2">
                <div className="flex justify-between text-sm">
                  <span className="text-red-600">Critical</span>
                  <span>{specs.rules_by_severity.critical || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-yellow-600">Warning</span>
                  <span>{specs.rules_by_severity.warning || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-blue-600">Info</span>
                  <span>{specs.rules_by_severity.info || 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Rules by Source */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Rules by Source</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(specs.rules_by_source).map(([source, count]) => (
                <div key={source} className="p-3 bg-gray-50 rounded">
                  <p className="font-medium">{source}</p>
                  <p className="text-2xl font-bold text-primary-600">{count}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Rules by Category */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Rules by Category</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(specs.rules_by_category).map(([category, count]) => (
                <div key={category} className="p-3 bg-gray-50 rounded">
                  <p className="font-medium capitalize">{category}</p>
                  <p className="text-2xl font-bold text-primary-600">{count}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'rules' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="bg-white p-4 rounded-lg shadow flex flex-wrap gap-4 items-center">
            <select
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              className="px-3 py-2 border rounded-lg"
            >
              <option value="">All Sources</option>
              {specs && Object.keys(specs.rules_by_source).map(source => (
                <option key={source} value={source}>{source}</option>
              ))}
            </select>
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="px-3 py-2 border rounded-lg"
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
            <span className="text-gray-500 text-sm">
              Showing {filteredRules.length} of {rules.length} rules
            </span>
          </div>

          {/* Rules List */}
          <div className="space-y-2">
            {filteredRules.map((rule, idx) => (
              <div key={rule.id} className="bg-white rounded-lg shadow overflow-hidden">
                <div
                  className="p-4 cursor-pointer hover:bg-gray-50"
                  onClick={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}
                >
                  <div className="flex items-start gap-3">
                    {getSeverityIcon(rule.severity)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">{rule.id}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityBadgeClass(rule.severity)}`}>
                          {rule.severity}
                        </span>
                        <span className="text-gray-400 text-xs">{rule.source}</span>
                      </div>
                      <p className="text-gray-600 text-sm">{rule.description}</p>
                    </div>
                    {expandedRule === rule.id ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                  </div>
                </div>
                
                {expandedRule === rule.id && (
                  <div className="border-t p-4 bg-gray-50 space-y-3">
                    <div>
                      <span className="text-sm font-medium text-gray-700">Category:</span>
                      <span className="ml-2 text-sm text-gray-600 capitalize">{rule.category}</span>
                    </div>
                    {rule.patterns.length > 0 && (
                      <div>
                        <span className="text-sm font-medium text-gray-700">Patterns:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {rule.patterns.map((p, i) => (
                            <code key={i} className="px-2 py-1 bg-gray-200 rounded text-xs">{p}</code>
                          ))}
                        </div>
                      </div>
                    )}
                    {rule.must_contain.length > 0 && (
                      <div>
                        <span className="text-sm font-medium text-gray-700">Must Contain:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {rule.must_contain.map((m, i) => (
                            <span key={i} className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">{m}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {rule.recommendation && (
                      <div>
                        <span className="text-sm font-medium text-gray-700">Recommendation:</span>
                        <p className="text-sm text-gray-600 mt-1">{rule.recommendation}</p>
                      </div>
                    )}
                    <div>
                      <span className="text-sm font-medium text-gray-700">Languages:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {rule.languages.map((l, i) => (
                          <span key={i} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">{l}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'add-eip' && (
        <div className="space-y-6">
          {/* Search EIPs */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Search EIPs</h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Search by EIP number or keyword..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="flex-1 px-4 py-2 border rounded-lg"
              />
              <button
                onClick={handleSearch}
                disabled={searching}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
              >
                <Search size={18} />
                Search
              </button>
            </div>
            
            {searchResults.length > 0 && (
              <div className="mt-4 space-y-2">
                {searchResults.map(result => (
                  <div key={result.number} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <span className="font-medium">EIP-{result.number}</span>
                      <span className="text-gray-600 ml-2">{result.title}</span>
                      {result.cached && <span className="ml-2 text-xs text-green-600">(cached)</span>}
                    </div>
                    <button
                      onClick={() => handleLoadEIP(result.number)}
                      className="px-3 py-1 bg-primary-600 text-white rounded hover:bg-primary-700 text-sm"
                    >
                      Load
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Popular EIPs */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Popular EIPs</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {popularEIPs.map(eip => (
                <div key={eip.number} className="p-4 border rounded-lg hover:border-primary-600 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-bold">EIP-{eip.number}</p>
                      <p className="text-sm text-gray-600">{eip.title}</p>
                    </div>
                    <button
                      onClick={() => handleLoadEIP(eip.number)}
                      className="px-3 py-1 bg-gray-100 rounded hover:bg-primary-600 hover:text-white transition-colors text-sm"
                    >
                      Load
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'custom-rule' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-xl font-bold mb-6 text-gray-800">Add Custom Rule</h3>
          <div className="space-y-4 max-w-2xl">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rule ID *</label>
                <input
                  type="text"
                  value={customRule.id}
                  onChange={(e) => setCustomRule({ ...customRule, id: e.target.value })}
                  placeholder="e.g., CUSTOM-001"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
                <input
                  type="text"
                  value={customRule.source}
                  onChange={(e) => setCustomRule({ ...customRule, source: e.target.value })}
                  placeholder="e.g., custom, team-standards"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select
                  value={customRule.category}
                  onChange={(e) => setCustomRule({ ...customRule, category: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="general">General</option>
                  <option value="security">Security</option>
                  <option value="token">Token</option>
                  <option value="gas">Gas Optimization</option>
                  <option value="interface">Interface</option>
                  <option value="event">Event</option>
                  <option value="access_control">Access Control</option>
                  <option value="reentrancy">Reentrancy</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select
                  value={customRule.severity}
                  onChange={(e) => setCustomRule({ ...customRule, severity: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="critical">Critical</option>
                  <option value="warning">Warning</option>
                  <option value="info">Info</option>
                </select>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
              <textarea
                value={customRule.description}
                onChange={(e) => setCustomRule({ ...customRule, description: e.target.value })}
                placeholder="Describe what this rule checks for..."
                className="w-full px-3 py-2 border rounded-lg"
                rows={2}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Patterns (comma-separated regex)</label>
              <input
                type="text"
                value={customRule.patterns}
                onChange={(e) => setCustomRule({ ...customRule, patterns: e.target.value })}
                placeholder="e.g., func.*transfer, function\s+transfer"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Must Contain (comma-separated)</label>
              <input
                type="text"
                value={customRule.must_contain}
                onChange={(e) => setCustomRule({ ...customRule, must_contain: e.target.value })}
                placeholder="e.g., emit, Transfer, event"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Must Not Contain (comma-separated)</label>
              <input
                type="text"
                value={customRule.must_not_contain}
                onChange={(e) => setCustomRule({ ...customRule, must_not_contain: e.target.value })}
                placeholder="e.g., selfdestruct, delegatecall"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recommendation</label>
              <textarea
                value={customRule.recommendation}
                onChange={(e) => setCustomRule({ ...customRule, recommendation: e.target.value })}
                placeholder="How to fix this issue..."
                className="w-full px-3 py-2 border rounded-lg"
                rows={2}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Languages (comma-separated)</label>
              <input
                type="text"
                value={customRule.languages}
                onChange={(e) => setCustomRule({ ...customRule, languages: e.target.value })}
                placeholder="e.g., solidity, go, javascript"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            
            <button
              onClick={handleAddCustomRule}
              className="w-full px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center justify-center gap-2"
            >
              <Plus size={18} />
              Add Rule
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
