'use client';

import React, { useEffect, useState } from 'react';
import { getStatistics } from '../lib/api';
import { FileCode, GitBranch, Database, Code2 } from 'lucide-react';
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

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await getStatistics();
      setStats(data);
    } catch (error) {
      console.error('Failed to load statistics:', error);
    } finally {
      setLoading(false);
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
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Codebase Statistics</h2>

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

      {/* Graph Visualization */}
      <div className="mt-6">
        <GraphVisualization />
      </div>
    </div>
  );
}

