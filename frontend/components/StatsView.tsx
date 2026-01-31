'use client';

import React, { useEffect, useState } from 'react';
import { getStatistics, listPRGraphs, deletePRGraph, PRGraphMetadata, getGraphDataFromStorage } from '../lib/api';
import { FileCode, GitBranch, Database, Code2, RefreshCw, Trash2, GitPullRequest, ExternalLink, FolderOpen, Layers } from 'lucide-react';
import dynamic from 'next/dynamic';

// Dynamically import GraphVisualization to avoid SSR issues with vis-network
const GraphVisualization = dynamic(() => import('./GraphVisualization'), {
  ssr: false,
  loading: () => (
    <div className="bg-white p-6 rounded-lg shadow-lg h-[600px] flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
    </div>
  ),
});

interface Statistics {
  total_files: number;
  total_entities: number;
  total_relationships: number;
  languages: Record<string, number>;
  entity_types: Record<string, number>;
  relationship_types: Record<string, number>;
}

type StorageSource = 'local' | 'pr';

export default function StatsView() {
  const [stats, setStats] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [prGraphs, setPrGraphs] = useState<PRGraphMetadata[]>([]);
  const [loadingPrGraphs, setLoadingPrGraphs] = useState(false);
  
  // Storage selection state
  const [activeStorage, setActiveStorage] = useState<StorageSource>('local');
  const [selectedPrGraph, setSelectedPrGraph] = useState<string | null>(null);
  const [graphLoadTrigger, setGraphLoadTrigger] = useState(0);
  const [currentGraphSource, setCurrentGraphSource] = useState<{ type: StorageSource; id?: string } | null>(null);

  useEffect(() => {
    loadStats();
    loadPrGraphs();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await getStatistics();
      setStats(data);
    } catch (error) {
      console.error('Failed to load statistics:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPrGraphs = async () => {
    setLoadingPrGraphs(true);
    try {
      const data = await listPRGraphs();
      setPrGraphs(data.graphs || []);
    } catch (error) {
      console.error('Failed to load PR graphs:', error);
    } finally {
      setLoadingPrGraphs(false);
    }
  };

  const handleLoadLocalGraph = () => {
    setCurrentGraphSource({ type: 'local' });
    setSelectedPrGraph(null);
    setGraphLoadTrigger(prev => prev + 1);
  };

  const handleLoadPrGraph = (prId: string) => {
    setCurrentGraphSource({ type: 'pr', id: prId });
    setSelectedPrGraph(prId);
    setGraphLoadTrigger(prev => prev + 1);
  };

  const handleDeletePrGraph = async (prId: string) => {
    if (!confirm('Delete this PR analysis graph?')) return;
    
    try {
      await deletePRGraph(prId);
      await loadPrGraphs();
      // Clear selection if deleted graph was selected
      if (selectedPrGraph === prId) {
        setSelectedPrGraph(null);
        setCurrentGraphSource(null);
      }
    } catch (error) {
      console.error('Failed to delete PR graph:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-gray-800">Codebase Statistics</h2>
        <button
          onClick={() => { loadStats(); loadPrGraphs(); }}
          disabled={loading}
          className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-2 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Storage Selection Tabs */}
      <div className="mb-6">
        <div className="flex gap-2 p-1 bg-gray-100 rounded-lg w-fit">
          <button
            onClick={() => setActiveStorage('local')}
            className={`px-4 py-2 rounded-md flex items-center gap-2 transition ${
              activeStorage === 'local'
                ? 'bg-white shadow text-blue-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            <FolderOpen className="w-4 h-4" />
            Local/Uploaded Code
          </button>
          <button
            onClick={() => setActiveStorage('pr')}
            className={`px-4 py-2 rounded-md flex items-center gap-2 transition ${
              activeStorage === 'pr'
                ? 'bg-white shadow text-purple-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            <GitPullRequest className="w-4 h-4" />
            PR Analysis Graphs
            {prGraphs.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">
                {prGraphs.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Local Storage Section */}
      {activeStorage === 'local' && (
        <div className="space-y-6">
          {/* Stats Summary */}
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-blue-600" />
                <h3 className="text-xl font-bold text-gray-800">Indexed Codebase (graph_storage)</h3>
              </div>
              <button
                onClick={handleLoadLocalGraph}
                disabled={!stats || stats.total_entities === 0}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <Database className="w-4 h-4" />
                Load Graph
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Code indexed via the Upload tab (ZIP files or local folder paths).
            </p>
            
            {stats && stats.total_entities > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <FileCode className="w-4 h-4 text-blue-600" />
                    <span className="text-sm text-gray-600">Files</span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{stats.total_files}</p>
                </div>
                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <Code2 className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-600">Entities</span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{stats.total_entities}</p>
                </div>
                <div className="p-4 bg-purple-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <GitBranch className="w-4 h-4 text-purple-600" />
                    <span className="text-sm text-gray-600">Relationships</span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{stats.total_relationships}</p>
                </div>
                <div className="p-4 bg-orange-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <Database className="w-4 h-4 text-orange-600" />
                    <span className="text-sm text-gray-600">Languages</span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{Object.keys(stats.languages || {}).length}</p>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <FolderOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No local codebase indexed yet.</p>
                <p className="text-sm">Use the Upload tab to index a codebase.</p>
              </div>
            )}
          </div>

          {/* Detailed Breakdown */}
          {stats && stats.total_entities > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-lg">
                <h3 className="text-lg font-bold mb-4 text-gray-800">By Entity Type</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {Object.entries(stats.entity_types || {}).map(([type, count]) => (
                    <div key={type} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                      <span className="font-medium capitalize text-sm">{type}</span>
                      <span className="text-gray-600 text-sm">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-lg">
                <h3 className="text-lg font-bold mb-4 text-gray-800">By Language</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {Object.entries(stats.languages || {}).map(([lang, count]) => (
                    <div key={lang} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                      <span className="font-medium uppercase text-sm">{lang}</span>
                      <span className="text-gray-600 text-sm">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* PR Graphs Section */}
      {activeStorage === 'pr' && (
        <div className="bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <GitPullRequest className="w-5 h-5 text-purple-600" />
              <h3 className="text-xl font-bold text-gray-800">PR Analysis Graphs (pr_graph_storage)</h3>
            </div>
            <span className="text-sm text-gray-500">{prGraphs.length} saved</span>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Code graphs from GitHub PR deep analysis. Select one to visualize.
          </p>
          
          {loadingPrGraphs ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
            </div>
          ) : prGraphs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <GitPullRequest className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No PR analysis graphs saved yet.</p>
              <p className="text-sm">Run a deep PR analysis to generate graphs.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {prGraphs.map((graph) => (
                <div 
                  key={graph.id} 
                  className={`flex items-center justify-between p-4 rounded-lg border-2 transition cursor-pointer ${
                    selectedPrGraph === graph.id
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 bg-gray-50 hover:border-purple-300'
                  }`}
                  onClick={() => handleLoadPrGraph(graph.id)}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{graph.owner}/{graph.repo}</span>
                      <span className="text-purple-600 font-semibold">#{graph.pr_number}</span>
                      {selectedPrGraph === graph.id && (
                        <span className="px-2 py-0.5 bg-purple-600 text-white text-xs rounded-full">
                          Selected
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 mt-1 flex flex-wrap gap-x-3">
                      <span>Commit: {graph.commit_sha?.substring(0, 7)}</span>
                      <span>{graph.stats?.total_entities?.toLocaleString() || 0} entities</span>
                      <span>{graph.stats?.total_relationships?.toLocaleString() || 0} relationships</span>
                      <span>{new Date(graph.timestamp).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    <a
                      href={`https://github.com/${graph.owner}/${graph.repo}/pull/${graph.pr_number}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-gray-500 hover:text-purple-600 transition"
                      title="View PR on GitHub"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                    <button
                      onClick={() => handleDeletePrGraph(graph.id)}
                      className="p-2 text-gray-500 hover:text-red-600 transition"
                      title="Delete this graph"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Graph Visualization - Always visible */}
      <div className="mt-6">
        {currentGraphSource ? (
          <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
            currentGraphSource.type === 'pr' ? 'bg-purple-50' : 'bg-blue-50'
          }`}>
            {currentGraphSource.type === 'local' ? (
              <>
                <FolderOpen className="w-4 h-4 text-blue-600" />
                <span className="text-sm">Viewing: <strong className="text-blue-700">Local/Uploaded Codebase (graph_storage)</strong></span>
              </>
            ) : (
              <>
                <GitPullRequest className="w-4 h-4 text-purple-600" />
                <span className="text-sm">Viewing: <strong className="text-purple-700">PR Graph - {currentGraphSource.id} (pr_graph_storage)</strong></span>
              </>
            )}
          </div>
        ) : (
          <div className="mb-4 p-3 bg-gray-50 rounded-lg flex items-center gap-2">
            <span className="text-sm text-gray-500">Click "Load Graph" above or select a PR graph to visualize</span>
          </div>
        )}
        <GraphVisualization 
          key="graph-vis"
          autoLoad={graphLoadTrigger > 0}
          storageSource={currentGraphSource?.type || 'local'}
          prGraphId={currentGraphSource?.type === 'pr' ? currentGraphSource.id : undefined}
          loadTrigger={graphLoadTrigger}
        />
      </div>
    </div>
  );
}
