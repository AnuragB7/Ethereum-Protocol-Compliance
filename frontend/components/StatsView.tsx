'use client';

import React, { useEffect, useState } from 'react';
import { getStatistics, listPRGraphs, loadPRGraphToMain, deletePRGraph, PRGraphMetadata } from '../lib/api';
import { FileCode, GitBranch, Database, Code2, RefreshCw, Trash2, Download, GitPullRequest, ExternalLink } from 'lucide-react';
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

export default function StatsView() {
  const [stats, setStats] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [prGraphs, setPrGraphs] = useState<PRGraphMetadata[]>([]);
  const [loadingPrGraphs, setLoadingPrGraphs] = useState(false);

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

  const handleLoadPrGraph = async (prId: string) => {
    try {
      await loadPRGraphToMain(prId);
      // Refresh stats after loading
      await loadStats();
    } catch (error) {
      console.error('Failed to load PR graph:', error);
    }
  };

  const handleDeletePrGraph = async (prId: string) => {
    if (!confirm('Delete this PR analysis graph?')) return;
    
    try {
      await deletePRGraph(prId);
      await loadPrGraphs();
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

  if (!stats) {
    return (
      <div className="text-center text-gray-500 py-12">
        No statistics available
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

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-600 text-sm font-medium">Total Files</h3>
            <FileCode className="text-primary-600" size={24} />
          </div>
          <p className="text-3xl font-bold text-gray-800">{stats.total_files}</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-600 text-sm font-medium">Code Entities</h3>
            <Code2 className="text-green-600" size={24} />
          </div>
          <p className="text-3xl font-bold text-gray-800">{stats.total_entities}</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-600 text-sm font-medium">Relationships</h3>
            <GitBranch className="text-blue-600" size={24} />
          </div>
          <p className="text-3xl font-bold text-gray-800">{stats.total_relationships}</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-600 text-sm font-medium">Languages</h3>
            <Database className="text-purple-600" size={24} />
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {Object.keys(stats.languages || {}).length}
          </p>
        </div>
      </div>

      {/* Breakdown tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Type */}
        <div className="bg-white p-6 rounded-lg shadow-lg">
          <h3 className="text-xl font-bold mb-4 text-gray-800">By Entity Type</h3>
          <div className="space-y-2">
            {Object.entries(stats.entity_types || {}).map(([type, count]) => (
              <div key={type} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <span className="font-medium capitalize">{type}</span>
                <span className="text-gray-600">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* By Language */}
        <div className="bg-white p-6 rounded-lg shadow-lg">
          <h3 className="text-xl font-bold mb-4 text-gray-800">By Language</h3>
          <div className="space-y-2">
            {Object.entries(stats.languages || {}).map(([lang, count]) => (
              <div key={lang} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <span className="font-medium uppercase">{lang}</span>
                <span className="text-gray-600">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Relationship Types */}
      <div className="mt-6 bg-white p-6 rounded-lg shadow-lg">
        <h3 className="text-xl font-bold mb-4 text-gray-800">Relationship Types</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Object.entries(stats.relationship_types || {}).map(([type, count]) => (
            <div key={type} className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="font-medium capitalize text-sm">{type}</span>
              <span className="text-gray-600">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* PR Analysis Graphs */}
      {prGraphs.length > 0 && (
        <div className="mt-6 bg-white p-6 rounded-lg shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <GitPullRequest className="w-5 h-5 text-purple-600" />
              <h3 className="text-xl font-bold text-gray-800">PR Analysis Graphs</h3>
            </div>
            <span className="text-sm text-gray-500">{prGraphs.length} saved</span>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            These are code graphs from PR deep analysis. Load one to visualize it below.
          </p>
          <div className="space-y-3">
            {prGraphs.map((graph) => (
              <div key={graph.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{graph.owner}/{graph.repo}</span>
                    <span className="text-purple-600">#{graph.pr_number}</span>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    <span>Commit: {graph.commit_sha?.substring(0, 7)}</span>
                    <span className="mx-2">•</span>
                    <span>{graph.stats?.total_entities || 0} entities</span>
                    <span className="mx-2">•</span>
                    <span>{graph.stats?.total_relationships || 0} relationships</span>
                    <span className="mx-2">•</span>
                    <span>{new Date(graph.timestamp).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
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
                    onClick={() => handleLoadPrGraph(graph.id)}
                    className="px-3 py-1.5 bg-purple-600 text-white rounded hover:bg-purple-700 transition flex items-center gap-1 text-sm"
                    title="Load this graph for visualization"
                  >
                    <Download className="w-4 h-4" />
                    Load
                  </button>
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
        </div>
      )}

      {/* Graph Visualization */}
      <div className="mt-6">
        <GraphVisualization />
      </div>
    </div>
  );
}

