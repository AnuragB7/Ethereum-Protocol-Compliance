'use client';

import React, { useEffect, useState } from 'react';
import { 
  listSpecifications, 
  fetchEIP, 
  searchEIPs, 
  uploadSpecification,
  addCustomRule,
  getComplianceRules
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
  ChevronRight
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

export default function SpecificationManager() {
  const [specs, setSpecs] = useState<SpecSummary | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EIPSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'rules' | 'add-eip' | 'custom-rule'>('overview');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);
  const [filterSource, setFilterSource] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  
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
  }, []);

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
      <div className="flex border-b mb-6">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-6 py-3 font-medium ${activeTab === 'overview' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('rules')}
          className={`px-6 py-3 font-medium ${activeTab === 'rules' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Rules ({rules.length})
        </button>
        <button
          onClick={() => setActiveTab('add-eip')}
          className={`px-6 py-3 font-medium ${activeTab === 'add-eip' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Add EIP
        </button>
        <button
          onClick={() => setActiveTab('custom-rule')}
          className={`px-6 py-3 font-medium ${activeTab === 'custom-rule' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Custom Rule
        </button>
      </div>

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
