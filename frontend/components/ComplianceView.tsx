'use client';

import React, { useEffect, useState } from 'react';
import { 
  getComplianceSummary, 
  getComplianceReport, 
  getComplianceDeviations,
  checkCompliance 
} from '../lib/api';
import { 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  Info, 
  FileCode, 
  Filter,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink
} from 'lucide-react';

interface Deviation {
  rule_id: string;
  rule_source: string;
  severity: string;
  category: string;
  description: string;
  file_path: string;
  line_number: number;
  code_snippet?: string;
  entity_name?: string;
  entity_type?: string;
  explanation: string;
  recommendation: string;
  confidence: number;
}

interface ComplianceSummary {
  status: string;
  compliance_score: number;
  total_entities: number;
  total_rules_checked: number;
  total_deviations: number;
  critical_issues: number;
  warnings: number;
  compliance_passed: boolean;
  most_common_issues: Array<{
    rule_id: string;
    description: string;
    severity: string;
    count: number;
  }>;
}

export default function ComplianceView() {
  const [summary, setSummary] = useState<ComplianceSummary | null>(null);
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState({
    severity: '',
    category: '',
    file: ''
  });
  const [expandedDeviation, setExpandedDeviation] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'summary' | 'deviations'>('summary');

  useEffect(() => {
    loadComplianceData();
  }, []);

  const loadComplianceData = async () => {
    try {
      setLoading(true);
      const [summaryData, deviationsData] = await Promise.all([
        getComplianceSummary(),
        getComplianceDeviations()
      ]);
      setSummary(summaryData);
      setDeviations(deviationsData.deviations || []);
    } catch (error) {
      console.error('Failed to load compliance data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadComplianceData();
    setRefreshing(false);
  };

  const filteredDeviations = deviations.filter(d => {
    if (filter.severity && d.severity !== filter.severity) return false;
    if (filter.category && d.category !== filter.category) return false;
    if (filter.file && !d.file_path.includes(filter.file)) return false;
    return true;
  });

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <ShieldAlert className="text-red-500" size={20} />;
      case 'warning':
        return <AlertTriangle className="text-yellow-500" size={20} />;
      default:
        return <Info className="text-blue-500" size={20} />;
    }
  };

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default:
        return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  const exportReport = async () => {
    try {
      const report = await getComplianceReport();
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance-report-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export report:', error);
    }
  };

  const uniqueCategories = [...new Set(deviations.map(d => d.category))];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!summary || summary.status === 'no_codebase') {
    return (
      <div className="text-center text-gray-500 py-12">
        <ShieldCheck size={48} className="mx-auto mb-4 opacity-50" />
        <p>No codebase indexed. Upload a codebase first to run compliance checks.</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold text-gray-800">Ethereum Compliance</h2>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={exportReport}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Download size={18} />
            Export Report
          </button>
        </div>
      </div>

      {/* Compliance Score Card */}
      <div className={`p-6 rounded-lg shadow-lg mb-6 ${summary.compliance_passed ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {summary.compliance_passed ? (
              <ShieldCheck size={48} className="text-green-600" />
            ) : (
              <ShieldAlert size={48} className="text-red-600" />
            )}
            <div>
              <h3 className="text-2xl font-bold">{summary.compliance_passed ? 'Compliance Passed' : 'Compliance Issues Found'}</h3>
              <p className="text-gray-600">
                Score: <span className="font-bold">{summary.compliance_score?.toFixed(1) || 0}%</span>
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-600">Entities Analyzed: {summary.total_entities}</p>
            <p className="text-sm text-gray-600">Rules Checked: {summary.total_rules_checked}</p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Total Deviations</span>
            <span className="text-2xl font-bold">{summary.total_deviations}</span>
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border-l-4 border-red-500">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Critical</span>
            <span className="text-2xl font-bold text-red-600">{summary.critical_issues}</span>
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border-l-4 border-yellow-500">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Warnings</span>
            <span className="text-2xl font-bold text-yellow-600">{summary.warnings}</span>
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Info</span>
            <span className="text-2xl font-bold text-blue-600">
              {summary.total_deviations - summary.critical_issues - summary.warnings}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        <button
          onClick={() => setActiveTab('summary')}
          className={`px-6 py-3 font-medium ${activeTab === 'summary' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Summary
        </button>
        <button
          onClick={() => setActiveTab('deviations')}
          className={`px-6 py-3 font-medium ${activeTab === 'deviations' ? 'border-b-2 border-primary-600 text-primary-600' : 'text-gray-500'}`}
        >
          Deviations ({deviations.length})
        </button>
      </div>

      {activeTab === 'summary' && (
        <div className="space-y-6">
          {/* Most Common Issues */}
          {summary.most_common_issues && summary.most_common_issues.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-xl font-bold mb-4 text-gray-800">Most Common Issues</h3>
              <div className="space-y-3">
                {summary.most_common_issues.map((issue, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div className="flex items-center gap-3">
                      {getSeverityIcon(issue.severity)}
                      <div>
                        <span className="font-medium">{issue.rule_id}</span>
                        <p className="text-sm text-gray-600">{issue.description}</p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getSeverityBadgeClass(issue.severity)}`}>
                      {issue.count} occurrences
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'deviations' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="bg-white p-4 rounded-lg shadow flex flex-wrap gap-4 items-center">
            <Filter size={20} className="text-gray-500" />
            <select
              value={filter.severity}
              onChange={(e) => setFilter({ ...filter, severity: e.target.value })}
              className="px-3 py-2 border rounded-lg"
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
            <select
              value={filter.category}
              onChange={(e) => setFilter({ ...filter, category: e.target.value })}
              className="px-3 py-2 border rounded-lg"
            >
              <option value="">All Categories</option>
              {uniqueCategories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Filter by file..."
              value={filter.file}
              onChange={(e) => setFilter({ ...filter, file: e.target.value })}
              className="px-3 py-2 border rounded-lg flex-1 min-w-[200px]"
            />
            <span className="text-gray-500 text-sm">
              Showing {filteredDeviations.length} of {deviations.length}
            </span>
          </div>

          {/* Deviations List */}
          <div className="space-y-3">
            {filteredDeviations.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <ShieldCheck size={48} className="mx-auto mb-4 opacity-50" />
                <p>No deviations found matching the current filters.</p>
              </div>
            ) : (
              filteredDeviations.map((deviation, idx) => (
                <div key={idx} className="bg-white rounded-lg shadow overflow-hidden">
                  <div
                    className="p-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedDeviation(expandedDeviation === `${idx}` ? null : `${idx}`)}
                  >
                    <div className="flex items-start gap-3">
                      {getSeverityIcon(deviation.severity)}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityBadgeClass(deviation.severity)}`}>
                            {deviation.severity.toUpperCase()}
                          </span>
                          <span className="text-gray-500 text-sm">{deviation.rule_id}</span>
                          <span className="text-gray-400 text-sm">|</span>
                          <span className="text-gray-500 text-sm">{deviation.category}</span>
                        </div>
                        <p className="font-medium text-gray-800">{deviation.description}</p>
                        <div className="flex items-center gap-2 mt-2 text-sm text-gray-600">
                          <FileCode size={14} />
                          <span>{deviation.file_path}:{deviation.line_number}</span>
                          {deviation.entity_name && (
                            <>
                              <span className="text-gray-400">|</span>
                              <span>{deviation.entity_name} ({deviation.entity_type})</span>
                            </>
                          )}
                        </div>
                      </div>
                      {expandedDeviation === `${idx}` ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                    </div>
                  </div>
                  
                  {expandedDeviation === `${idx}` && (
                    <div className="border-t p-4 bg-gray-50">
                      <div className="space-y-4">
                        {deviation.explanation && (
                          <div>
                            <h4 className="font-medium text-gray-700 mb-1">Issue</h4>
                            <p className="text-gray-600">{deviation.explanation}</p>
                          </div>
                        )}
                        {deviation.recommendation && (
                          <div>
                            <h4 className="font-medium text-gray-700 mb-1">Recommendation</h4>
                            <p className="text-gray-600">{deviation.recommendation}</p>
                          </div>
                        )}
                        {deviation.code_snippet && (
                          <div>
                            <h4 className="font-medium text-gray-700 mb-1">Code</h4>
                            <pre className="bg-gray-800 text-gray-100 p-3 rounded overflow-x-auto text-sm">
                              {deviation.code_snippet}
                            </pre>
                          </div>
                        )}
                        <div className="flex items-center gap-4 text-sm text-gray-500">
                          <span>Source: {deviation.rule_source}</span>
                          <span>Confidence: {(deviation.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
