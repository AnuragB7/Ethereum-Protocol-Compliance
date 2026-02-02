'use client';

import React, { useState, useEffect } from 'react';
import { Settings, Upload, BarChart3, Save, Book, GitBranch, ShieldCheck, Info } from 'lucide-react';
import UploadStep from '../components/UploadStep';
import StatsView from '../components/StatsView';
import SpecificationManager from '../components/SpecificationManager';
import GitAnalysisView from '../components/GitAnalysisView';
import PRAnalysisView from '../components/PRAnalysisView';
import { configureAPI, healthCheck, APIConfig } from '../lib/api';
import '../styles/globals.css';

type View = 'config' | 'upload' | 'stats' | 'specs' | 'git' | 'llm-compliance-analysis';
type Provider = 'openai' | 'anthropic';

// Default models for each provider
const DEFAULT_MODELS: Record<Provider, { llm: string; embed: string }> = {
  openai: { llm: 'gpt-4', embed: 'text-embedding-ada-002' },
  anthropic: { llm: 'claude-sonnet-4-20250514', embed: 'text-embedding-ada-002' }
};

export default function Home() {
  const [currentView, setCurrentView] = useState<View>('config');
  const [configured, setConfigured] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [provider, setProvider] = useState<Provider>('openai');
  const [apiConfig, setApiConfig] = useState<APIConfig>({
    provider: 'openai',
    api_key: '',
    api_base: '',
    llm_model: 'gpt-4',
    embed_model: 'text-embedding-ada-002',
    embed_api_key: '',
    embed_api_base: '',
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
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
        setCurrentView('stats');
      }
    } catch (err) {
      console.log('API not ready yet');
    }
  };

  // Handle provider change
  const handleProviderChange = (newProvider: Provider) => {
    setProvider(newProvider);
    setApiConfig(prev => ({
      ...prev,
      provider: newProvider,
      llm_model: DEFAULT_MODELS[newProvider].llm,
      // Clear api_base when switching to Anthropic (not needed)
      api_base: newProvider === 'anthropic' ? '' : prev.api_base,
    }));
  };

  const handleConfigure = async () => {
    // Validate required fields based on provider
    if (!apiConfig.api_key) {
      setError('API Key is required');
      return;
    }
    
    if (provider === 'openai' && !apiConfig.api_base) {
      setError('API Base URL is required for OpenAI provider');
      return;
    }
    
    // For Anthropic with embeddings, either use same key or require separate embedding key
    if (provider === 'anthropic' && !apiConfig.embed_api_key && !apiConfig.api_key) {
      setError('Embedding API Key is required (Anthropic does not support embeddings)');
      return;
    }

    setConfiguring(true);
    setError('');

    try {
      const configToSend: APIConfig = {
        ...apiConfig,
        provider,
        // For Anthropic, embeddings need OpenAI credentials
        embed_api_key: provider === 'anthropic' ? (apiConfig.embed_api_key || '') : undefined,
        embed_api_base: provider === 'anthropic' ? (apiConfig.embed_api_base || 'https://api.openai.com/v1') : undefined,
      };
      
      await configureAPI(configToSend);
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
    setCurrentView('stats');
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
                    onClick={() => setCurrentView('llm-compliance-analysis')}
                    className={`px-4 py-3 font-medium transition flex items-center gap-2 ${
                      currentView === 'llm-compliance-analysis'
                        ? 'border-b-2 border-purple-600 text-purple-600'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    <ShieldCheck size={18} />
                    Manual PR Compliance
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
                    Automated CI/CD
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
              {/* Provider Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  LLM Provider *
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => handleProviderChange('openai')}
                    className={`p-4 rounded-lg border-2 text-left transition ${
                      provider === 'openai'
                        ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-semibold text-gray-800">OpenAI / Compatible</div>
                    <div className="text-xs text-gray-500 mt-1">GPT-4, Azure, Local LLMs</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleProviderChange('anthropic')}
                    className={`p-4 rounded-lg border-2 text-left transition ${
                      provider === 'anthropic'
                        ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-semibold text-gray-800">Anthropic</div>
                    <div className="text-xs text-gray-500 mt-1">Claude 3.5, Claude 3</div>
                  </button>
                </div>
              </div>

              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {provider === 'anthropic' ? 'Anthropic API Key' : 'API Key'} *
                </label>
                <input
                  type="password"
                  value={apiConfig.api_key}
                  onChange={(e) =>
                    setApiConfig({ ...apiConfig, api_key: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder={provider === 'anthropic' ? 'sk-ant-...' : 'your-api-key'}
                />
              </div>

              {/* API Base URL - Only for OpenAI */}
              {provider === 'openai' && (
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
              )}

              {/* LLM Model */}
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
                  placeholder={DEFAULT_MODELS[provider].llm}
                />
                <p className="text-xs text-gray-500 mt-1">
                  {provider === 'anthropic' 
                    ? 'e.g., claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, claude-3-opus-20240229'
                    : 'e.g., gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo'
                  }
                </p>
              </div>
              {/* Embedding Model */}
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
                <p className="text-xs text-gray-500 mt-1">
                  Embeddings always use OpenAI API (text-embedding-ada-002 or text-embedding-3-small)
                </p>
              </div>

              {/* Anthropic Embedding Notice */}
              {provider === 'anthropic' && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Info size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-blue-800">
                        OpenAI API Key Required for Embeddings
                      </p>
                      <p className="text-sm text-blue-700 mt-1">
                        Anthropic doesn't provide embedding models. You'll need an OpenAI API key for embeddings.
                      </p>
                      <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="text-sm text-blue-600 hover:text-blue-800 mt-2 underline"
                      >
                        {showAdvanced ? 'Hide' : 'Show'} embedding configuration
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Advanced: Separate Embedding Credentials (for Anthropic) */}
              {provider === 'anthropic' && showAdvanced && (
                <div className="p-4 bg-gray-50 rounded-lg border space-y-3">
                  <p className="text-sm font-medium text-gray-700">Embedding API Configuration</p>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      OpenAI API Key (for embeddings)
                    </label>
                    <input
                      type="password"
                      value={apiConfig.embed_api_key || ''}
                      onChange={(e) =>
                        setApiConfig({ ...apiConfig, embed_api_key: e.target.value })
                      }
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder="sk-..."
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Leave empty to use the main API key (will fail if using Anthropic key)
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Embedding API Base URL
                    </label>
                    <input
                      type="text"
                      value={apiConfig.embed_api_base || ''}
                      onChange={(e) =>
                        setApiConfig({ ...apiConfig, embed_api_base: e.target.value })
                      }
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder="https://api.openai.com/v1"
                    />
                  </div>
                </div>
              )}

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

        {currentView === 'stats' && uploaded && <StatsView />}

        {currentView === 'specs' && uploaded && <SpecificationManager />}

        {currentView === 'git' && uploaded && <GitAnalysisView />}

        {currentView === 'llm-compliance-analysis' && uploaded && <PRAnalysisView />}
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

