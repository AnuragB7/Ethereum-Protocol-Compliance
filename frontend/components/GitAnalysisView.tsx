'use client';

import React, { useState } from 'react';
import { 
  GitBranch, 
  GitCommit, 
  GitPullRequest,
  FolderGit,
  Loader,
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  Play
} from 'lucide-react';
import {
  analyzeCommit,
  analyzeRemoteCommit,
  analyzePullRequest,
  analyzeCommitRange
} from '../lib/api';

interface AnalysisResult {
  status: string;
  commit?: any;
  deviations?: any[];
  summary?: any;
  error?: string;
}

export default function GitAnalysisView() {
  const [activeTab, setActiveTab] = useState<'local' | 'remote' | 'pr'>('local');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  
  // Local repo form
  const [localRepo, setLocalRepo] = useState({
    path: '',
    commitHash: 'HEAD'
  });
  
  // Remote repo form
  const [remoteRepo, setRemoteRepo] = useState({
    url: '',
    commitHash: '',
    branch: 'main'
  });
  
  // PR form
  const [prForm, setPrForm] = useState({
    repoUrl: '',
    prNumber: ''
  });

  const handleAnalyzeLocal = async () => {
    if (!localRepo.path) {
      alert('Please enter the repository path');
      return;
    }
    
    setLoading(true);
    setResult(null);
    
    try {
      const data = await analyzeCommit(localRepo.path, localRepo.commitHash);
      setResult(data);
    } catch (error: any) {
      setResult({ 
        status: 'error', 
        error: error.response?.data?.detail || error.message || 'Analysis failed' 
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeRemote = async () => {
    if (!remoteRepo.url || !remoteRepo.commitHash) {
      alert('Please enter the repository URL and commit hash');
      return;
    }
    
    setLoading(true);
    setResult(null);
    
    try {
      const data = await analyzeRemoteCommit(
        remoteRepo.url, 
        remoteRepo.commitHash,
        remoteRepo.branch
      );
      setResult(data);
    } catch (error: any) {
      setResult({ 
        status: 'error', 
        error: error.response?.data?.detail || error.message || 'Analysis failed' 
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzePR = async () => {
    if (!prForm.repoUrl || !prForm.prNumber) {
      alert('Please enter the repository URL and PR number');
      return;
    }
    
    setLoading(true);
    setResult(null);
    
    try {
      const data = await analyzePullRequest(prForm.repoUrl, parseInt(prForm.prNumber));
      setResult(data);
    } catch (error: any) {
      setResult({ 
        status: 'error', 
        error: error.response?.data?.detail || error.message || 'Analysis failed' 
      });
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-blue-600 bg-blue-50';
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center gap-3 mb-6">
        <GitBranch size={32} className="text-primary-600" />
        <div>
          <h2 className="text-3xl font-bold text-gray-800">Git Analysis</h2>
          <p className="text-gray-600">Analyze commits and pull requests for Ethereum compliance</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        <button
          onClick={() => setActiveTab('local')}
          className={`px-6 py-3 font-medium flex items-center gap-2 ${
            activeTab === 'local' 
              ? 'border-b-2 border-primary-600 text-primary-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <FolderGit size={18} />
          Local Repository
        </button>
        <button
          onClick={() => setActiveTab('remote')}
          className={`px-6 py-3 font-medium flex items-center gap-2 ${
            activeTab === 'remote' 
              ? 'border-b-2 border-primary-600 text-primary-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <GitCommit size={18} />
          Remote Commit
        </button>
        <button
          onClick={() => setActiveTab('pr')}
          className={`px-6 py-3 font-medium flex items-center gap-2 ${
            activeTab === 'pr' 
              ? 'border-b-2 border-primary-600 text-primary-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <GitPullRequest size={18} />
          Pull Request
        </button>
      </div>

      {/* Local Repository Tab */}
      {activeTab === 'local' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-xl font-semibold mb-4">Analyze Local Repository</h3>
          <p className="text-gray-600 mb-4">
            Enter the path to a local Git repository on your machine.
          </p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Repository Path *
              </label>
              <input
                type="text"
                value={localRepo.path}
                onChange={(e) => setLocalRepo({ ...localRepo, path: e.target.value })}
                placeholder="/path/to/your/git/repository"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Commit Hash (default: HEAD)
              </label>
              <input
                type="text"
                value={localRepo.commitHash}
                onChange={(e) => setLocalRepo({ ...localRepo, commitHash: e.target.value })}
                placeholder="HEAD or specific commit hash"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            
            <button
              onClick={handleAnalyzeLocal}
              disabled={loading}
              className="w-full py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play size={20} />
                  Analyze Commit
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Remote Commit Tab */}
      {activeTab === 'remote' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-xl font-semibold mb-4">Analyze Remote Commit</h3>
          <p className="text-gray-600 mb-4">
            Enter a GitHub/GitLab repository URL and commit hash to analyze.
          </p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Repository URL *
              </label>
              <input
                type="text"
                value={remoteRepo.url}
                onChange={(e) => setRemoteRepo({ ...remoteRepo, url: e.target.value })}
                placeholder="https://github.com/owner/repo"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Commit Hash *
                </label>
                <input
                  type="text"
                  value={remoteRepo.commitHash}
                  onChange={(e) => setRemoteRepo({ ...remoteRepo, commitHash: e.target.value })}
                  placeholder="abc123..."
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Branch
                </label>
                <input
                  type="text"
                  value={remoteRepo.branch}
                  onChange={(e) => setRemoteRepo({ ...remoteRepo, branch: e.target.value })}
                  placeholder="main"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            
            <button
              onClick={handleAnalyzeRemote}
              disabled={loading}
              className="w-full py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play size={20} />
                  Analyze Remote Commit
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Pull Request Tab */}
      {activeTab === 'pr' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-xl font-semibold mb-4">Analyze Pull Request</h3>
          <p className="text-gray-600 mb-4">
            Enter a GitHub repository URL and PR number to analyze all changes.
          </p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Repository URL *
              </label>
              <input
                type="text"
                value={prForm.repoUrl}
                onChange={(e) => setPrForm({ ...prForm, repoUrl: e.target.value })}
                placeholder="https://github.com/owner/repo"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Pull Request Number *
              </label>
              <input
                type="text"
                value={prForm.prNumber}
                onChange={(e) => setPrForm({ ...prForm, prNumber: e.target.value })}
                placeholder="123"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            
            <button
              onClick={handleAnalyzePR}
              disabled={loading}
              className="w-full py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play size={20} />
                  Analyze Pull Request
                </>
              )}
            </button>
          </div>
          
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>Note:</strong> For private repositories, you may need to provide a GitHub token.
              Set the <code className="bg-blue-100 px-1 rounded">GITHUB_TOKEN</code> environment variable.
            </p>
          </div>
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="mt-6">
          {result.status === 'error' ? (
            <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
              <div className="flex items-center gap-2 text-red-800">
                <AlertTriangle size={20} />
                <span className="font-semibold">Analysis Failed</span>
              </div>
              <p className="mt-2 text-red-700">{result.error}</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="p-4 bg-gray-50 border-b">
                <div className="flex items-center gap-2">
                  {result.summary?.compliance_passed ? (
                    <CheckCircle className="text-green-600" size={24} />
                  ) : (
                    <AlertTriangle className="text-yellow-600" size={24} />
                  )}
                  <h3 className="text-xl font-semibold">Analysis Results</h3>
                </div>
                
                {result.commit && (
                  <div className="mt-2 text-sm text-gray-600">
                    <p><strong>Commit:</strong> {result.commit.hash?.substring(0, 8)}</p>
                    <p><strong>Author:</strong> {result.commit.author}</p>
                    <p><strong>Message:</strong> {result.commit.message}</p>
                  </div>
                )}
              </div>
              
              {result.summary && (
                <div className="p-4 border-b">
                  <div className="grid grid-cols-4 gap-4">
                    <div className="text-center p-3 bg-gray-50 rounded">
                      <p className="text-2xl font-bold">{result.summary.compliance_score?.toFixed(0) || 0}%</p>
                      <p className="text-sm text-gray-600">Score</p>
                    </div>
                    <div className="text-center p-3 bg-red-50 rounded">
                      <p className="text-2xl font-bold text-red-600">{result.summary.critical_issues || 0}</p>
                      <p className="text-sm text-gray-600">Critical</p>
                    </div>
                    <div className="text-center p-3 bg-yellow-50 rounded">
                      <p className="text-2xl font-bold text-yellow-600">{result.summary.warnings || 0}</p>
                      <p className="text-sm text-gray-600">Warnings</p>
                    </div>
                    <div className="text-center p-3 bg-blue-50 rounded">
                      <p className="text-2xl font-bold text-blue-600">{result.summary.total_deviations || 0}</p>
                      <p className="text-sm text-gray-600">Total Issues</p>
                    </div>
                  </div>
                </div>
              )}
              
              {result.deviations && result.deviations.length > 0 && (
                <div className="p-4">
                  <h4 className="font-semibold mb-3">Deviations Found ({result.deviations.length})</h4>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {result.deviations.map((deviation: any, idx: number) => (
                      <div key={idx} className={`p-3 rounded ${getSeverityColor(deviation.severity)}`}>
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="font-medium">{deviation.rule_id}</span>
                            <span className="mx-2 text-gray-400">|</span>
                            <span className="text-sm">{deviation.category}</span>
                          </div>
                          <span className="text-xs uppercase font-semibold">{deviation.severity}</span>
                        </div>
                        <p className="text-sm mt-1">{deviation.description}</p>
                        {deviation.file_path && (
                          <p className="text-xs mt-1 opacity-75">
                            {deviation.file_path}:{deviation.line_number}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {(!result.deviations || result.deviations.length === 0) && (
                <div className="p-8 text-center text-gray-500">
                  <CheckCircle size={48} className="mx-auto mb-4 text-green-500" />
                  <p>No compliance issues found!</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Webhook Setup Info */}
      <div className="mt-8 bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Automatic Analysis with Webhooks</h3>
        <p className="text-gray-600 mb-4">
          Set up webhooks to automatically analyze commits and PRs when they're pushed.
        </p>
        
        <div className="space-y-3">
          <div className="p-3 bg-white rounded border">
            <p className="font-medium">GitHub Webhook URL</p>
            <code className="text-sm text-primary-600">
              {typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000'}/api/webhook/github
            </code>
          </div>
          
          <div className="p-3 bg-white rounded border">
            <p className="font-medium">GitLab Webhook URL</p>
            <code className="text-sm text-primary-600">
              {typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000'}/api/webhook/gitlab
            </code>
          </div>
        </div>
        
        <div className="mt-4 text-sm text-gray-600">
          <p><strong>Setup Instructions:</strong></p>
          <ol className="list-decimal list-inside mt-2 space-y-1">
            <li>Go to your repository settings → Webhooks</li>
            <li>Add the appropriate webhook URL above</li>
            <li>Set content type to <code className="bg-gray-200 px-1 rounded">application/json</code></li>
            <li>Select events: <em>Push</em> and <em>Pull Request</em></li>
            <li>Optionally set a secret and configure it in your <code>.env</code> file</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
