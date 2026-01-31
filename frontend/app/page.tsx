'use client';

import React, { useState, useEffect } from 'react';
import { Settings, Upload, Search, BarChart3, Save, ShieldCheck, Book, GitBranch, Zap, GitPullRequest } from 'lucide-react';
import UploadStep from '../components/UploadStep';
import AnalysisView from '../components/AnalysisView';
import QueryView from '../components/QueryView';
import StatsView from '../components/StatsView';
import ComplianceView from '../components/ComplianceView';
import SpecificationManager from '../components/SpecificationManager';
import GitAnalysisView from '../components/GitAnalysisView';
import LLMComplianceView from '../components/LLMComplianceView';
import PRAnalysisView from '../components/PRAnalysisView';
import { configureAPI, healthCheck } from '../lib/api';
import '../styles/globals.css';

type View = 'config' | 'upload' | 'analysis' | 'query' | 'stats' | 'compliance' | 'specs' | 'git' | 'llm-compliance' | 'pr-analysis';

export default function Home() {
  const [currentView, setCurrentView] = useState<View>('config');
  const [configured, setConfigured] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [apiConfig, setApiConfig] = useState({
    api_key: '',
    api_base: '',
    llm_model: 'gpt-4.1',
    embed_model: 'text-embedding-ada-002',
  });
  const [configuring, setConfiguring] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    checkHealth();
    
    // Listen for navigation events from child components
    const handleNavigate = (event: CustomEvent<View>) => {
      if (event.detail) {
        setCurrentView(event.detail);
      }
    };
    
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => {
      window.removeEventListener('navigate', handleNavigate as EventListener);
    };
  }, []);

  const checkHealth = async () => {
    try {
      const health = await healthCheck();
      if (health.indexer_ready) {
        setConfigured(true);
        setUploaded(true);
        setCurrentView('analysis');
      }
    } catch (err) {
      console.log('API not ready yet');
    }
  };

  const handleConfigure = async () => {
    if (!apiConfig.api_key || !apiConfig.api_base) {
      setError('Please fill in all required fields');
      return;
    }

    setConfiguring(true);
    setError('');

    try {
      await configureAPI(apiConfig);
      setConfigured(true);
      setCurrentView('upload');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Configuration failed');
    } finally {
      setConfiguring(false);
    }
  };

  const handleUploadSuccess = (data: any) => {
    setUploaded(true);
    setCurrentView('analysis');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Code Analysis Platform
              </h1>
              <p className="text-sm text-gray-600">
                Multi-language codebase analysis powered by Property Graph RAG
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 rounded-full text-sm ${
                  uploaded
                    ? 'bg-green-100 text-green-700'
                    : configured
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {uploaded ? 'Ready' : configured ? 'Configured' : 'Not Configured'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      {configured && (
        <nav className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex gap-1">
              <button
                onClick={() => setCurrentView('config')}
                className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                  currentView === 'config'
                    ? 'border-b-2 border-primary-600 text-primary-600'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                <Settings size={18} />
                Config
              </button>
              <button
                onClick={() => setCurrentView('upload')}
                className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                  currentView === 'upload'
                    ? 'border-b-2 border-primary-600 text-primary-600'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                <Upload size={18} />
                Upload
              </button>
              {uploaded && (
                <>
                  <button
                    onClick={() => setCurrentView('analysis')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'analysis'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <Search size={18} />
                    Analysis
                  </button>
                  <button
                    onClick={() => setCurrentView('query')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'query'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <Search size={18} />
                    Ask Questions
                  </button>
                  <button
                    onClick={() => setCurrentView('stats')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'stats'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <BarChart3 size={18} />
                    Statistics
                  </button>
                  <button
                    onClick={() => setCurrentView('specs')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'specs'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <Book size={18} />
                    Specifications
                  </button>
                  <button
                    onClick={() => setCurrentView('compliance')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'compliance'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <ShieldCheck size={18} />
                    Compliance
                  </button>
                  <button
                    onClick={() => setCurrentView('git')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'git'
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <GitBranch size={18} />
                    Git Analysis
                  </button>
                  <button
                    onClick={() => setCurrentView('llm-compliance')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'llm-compliance'
                        ? 'border-b-2 border-purple-600 text-purple-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <Zap size={18} />
                    LLM Compliance
                  </button>
                  <button
                    onClick={() => setCurrentView('pr-analysis')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'pr-analysis'
                        ? 'border-b-2 border-purple-600 text-purple-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <GitPullRequest size={18} />
                    PR Analysis
                  </button>
                </>
              )}
            </div>
          </div>
        </nav>
      )}

      {/* Main content */}
      <main className="py-8">
        {currentView === 'config' && (
          <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">API Configuration</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Key *
                </label>
                <input
                  type="password"
                  value={apiConfig.api_key}
                  onChange={(e) =>
                    setApiConfig({ ...apiConfig, api_key: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="your-api-key"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Base URL *
                </label>
                <input
                  type="text"
                  value={apiConfig.api_base}
                  onChange={(e) =>
                    setApiConfig({ ...apiConfig, api_base: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="https://api.openai.com/v1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  LLM Model
                </label>
                <input
                  type="text"
                  value={apiConfig.llm_model}
                  onChange={(e) =>
                    setApiConfig({ ...apiConfig, llm_model: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="gpt-4.1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Embedding Model
                </label>
                <input
                  type="text"
                  value={apiConfig.embed_model}
                  onChange={(e) =>
                    setApiConfig({ ...apiConfig, embed_model: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="text-embedding-ada-002"
                />
              </div>

              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  {error}
                </div>
              )}

              <button
                onClick={handleConfigure}
                disabled={configuring}
                className="w-full py-3 px-4 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400 flex items-center justify-center gap-2"
              >
                <Save size={20} />
                {configuring ? 'Configuring...' : configured ? 'Update Configuration' : 'Save Configuration'}
              </button>
            </div>
          </div>
        )}

        {currentView === 'upload' && (
          <UploadStep onUploadSuccess={handleUploadSuccess} />
        )}

        {currentView === 'analysis' && uploaded && <AnalysisView />}

        {currentView === 'query' && uploaded && <QueryView />}

        {currentView === 'stats' && uploaded && <StatsView />}

        {currentView === 'specs' && uploaded && <SpecificationManager />}

        {currentView === 'compliance' && uploaded && <ComplianceView />}

        {currentView === 'git' && uploaded && <GitAnalysisView />}

        {currentView === 'llm-compliance' && uploaded && <LLMComplianceView />}

        {currentView === 'pr-analysis' && uploaded && <PRAnalysisView />}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <p className="text-center text-sm text-gray-600">
            Code Analysis Platform • Supports Python, Java, COBOL, JavaScript, TypeScript, Vue, and Go
          </p>
        </div>
      </footer>
    </div>
  );
}

