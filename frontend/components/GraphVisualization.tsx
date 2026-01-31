'use client';

import React, { useEffect, useRef, useState } from 'react';
import { getGraphData } from '../lib/api';

declare global {
  interface Window {
    vis: any;
  }
}

interface GraphNode {
  id: string;
  name?: string;
  label?: string;
  type?: string;
  language?: string;
  file_path?: string;
  line_start?: number;
  line_end?: number;
}

interface GraphEdge {
  source?: string;
  from?: string;
  target?: string;
  to?: string;
  relationship?: string;
  label?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface NodeInfo {
  id: string;
  name: string;
  type: string;
  language?: string;
  file_path?: string;
  line_start?: number;
  line_end?: number;
  connections: number;
}

interface GraphVisualizationProps {
  autoLoad?: boolean;
}

export default function GraphVisualization({ autoLoad = false }: GraphVisualizationProps) {
  const networkRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphStats, setGraphStats] = useState<{ nodes: number; edges: number } | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeInfo | null>(null);
  const [network, setNetwork] = useState<any>(null);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [visLoaded, setVisLoaded] = useState(false);
  const hasAutoLoaded = useRef(false);

  // Load vis-network library
  useEffect(() => {
    if (typeof window !== 'undefined' && !window.vis) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/vis-network@9.1.6/dist/vis-network.min.js';
      script.async = true;
      script.onload = () => setVisLoaded(true);
      document.body.appendChild(script);
    } else if (window.vis) {
      setVisLoaded(true);
    }
  }, []);

  // Auto-load graph when prop changes
  useEffect(() => {
    if (autoLoad && visLoaded && networkRef.current && !hasAutoLoaded.current) {
      hasAutoLoaded.current = true;
      loadGraph();
    }
  }, [autoLoad, visLoaded]);

  const loadGraph = async () => {
    if (!visLoaded || !networkRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const data: GraphData = await getGraphData();

      if (!data.nodes || !data.edges) {
        throw new Error('Invalid graph data received');
      }

      setGraphStats({ nodes: data.nodes.length, edges: data.edges.length });
      createNetwork(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load graph data');
      console.error('Error loading graph:', err);
    } finally {
      setLoading(false);
    }
  };

  const createNetwork = (data: GraphData) => {
    if (!networkRef.current || !window.vis) return;

    // Prepare nodes
    const nodesArray = data.nodes.map((node) => {
      let color, shape, size;

      switch (node.type) {
        case 'function':
        case 'method':
          color = '#4CAF50';
          shape = 'dot';
          size = 20;
          break;
        case 'class':
        case 'struct':
          color = '#2196F3';
          shape = 'diamond';
          size = 25;
          break;
        case 'interface':
          color = '#00BCD4';
          shape = 'triangle';
          size = 22;
          break;
        case 'package':
          color = '#FF9800';
          shape = 'box';
          size = 15;
          break;
        default:
          color = '#9C27B0';
          shape = 'dot';
          size = 15;
      }

      return {
        id: node.id,
        label: node.name || node.label || node.id,
        title: `Type: ${node.type || 'unknown'}\nName: ${node.name || node.id}`,
        color: color,
        shape: shape,
        size: size,
        font: { size: 12, color: '#333' },
        ...node,
      };
    });

    // Prepare edges
    const edgesArray = data.edges.map((edge) => ({
      from: edge.source || edge.from,
      to: edge.target || edge.to,
      label: edge.relationship || edge.label || '',
      arrows: 'to',
      color: { color: '#848484', highlight: '#667eea' },
      font: { size: 10, color: '#666', strokeWidth: 0 },
    }));

    const nodes = new window.vis.DataSet(nodesArray);
    const edges = new window.vis.DataSet(edgesArray);

    const graphData = { nodes, edges };

    const options = {
      nodes: {
        borderWidth: 2,
        borderWidthSelected: 4,
        font: { size: 14, face: 'arial' },
      },
      edges: {
        width: 2,
        smooth: { type: 'continuous', roundness: 0.5 },
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -8000,
          centralGravity: 0.3,
          springLength: 150,
          springConstant: 0.04,
          damping: 0.09,
          avoidOverlap: 0.1,
        },
        stabilization: { iterations: 200, updateInterval: 25 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true,
      },
    };

    const net = new window.vis.Network(networkRef.current, graphData, options);
    setNetwork(net);

    // Event listeners
    net.on('click', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = nodes.get(nodeId);
        const connectedEdges = net.getConnectedEdges(nodeId);
        setSelectedNode({
          id: node.id,
          name: node.name || node.label || 'N/A',
          type: node.type || 'unknown',
          language: node.language,
          file_path: node.file_path,
          line_start: node.line_start,
          line_end: node.line_end,
          connections: connectedEdges.length,
        });
      }
    });

    net.on('stabilizationIterationsDone', () => {
      net.setOptions({ physics: { enabled: false } });
      setPhysicsEnabled(false);
    });
  };

  const fitNetwork = () => {
    if (network) {
      network.fit({
        animation: { duration: 1000, easingFunction: 'easeInOutQuad' },
      });
    }
  };

  const togglePhysics = () => {
    if (network) {
      const newState = !physicsEnabled;
      network.setOptions({ physics: { enabled: newState } });
      setPhysicsEnabled(newState);
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">Property Graph Visualization</h3>
        <div className="flex gap-2">
          <button
            onClick={loadGraph}
            disabled={loading || !visLoaded}
            className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading...
              </span>
            ) : (
              '📊 Load Graph'
            )}
          </button>
          {graphStats && (
            <>
              <button
                onClick={fitNetwork}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-all"
              >
                🔍 Fit View
              </button>
              <button
                onClick={togglePhysics}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-all"
              >
                ⚡ {physicsEnabled ? 'Disable' : 'Enable'} Physics
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          {error}
        </div>
      )}

      {graphStats && (
        <div className="mb-4 grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white p-3 rounded-lg text-center">
            <div className="text-2xl font-bold">{graphStats.nodes}</div>
            <div className="text-sm opacity-90">Nodes</div>
          </div>
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white p-3 rounded-lg text-center">
            <div className="text-2xl font-bold">{graphStats.edges}</div>
            <div className="text-sm opacity-90">Edges</div>
          </div>
        </div>
      )}

      {/* Legend */}
      {graphStats && (
        <div className="mb-4 flex flex-wrap gap-4 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-green-500 border-2 border-gray-700"></div>
            <span className="text-sm">Functions/Methods</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-500 border-2 border-gray-700" style={{ transform: 'rotate(45deg)' }}></div>
            <span className="text-sm">Classes/Structs</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-0 h-0 border-l-[8px] border-r-[8px] border-b-[14px] border-l-transparent border-r-transparent border-b-cyan-500"></div>
            <span className="text-sm">Interfaces</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-orange-500 border-2 border-gray-700"></div>
            <span className="text-sm">Packages</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-purple-500 border-2 border-gray-700"></div>
            <span className="text-sm">Other</span>
          </div>
        </div>
      )}

      {/* Network container */}
      <div
        ref={networkRef}
        className="w-full h-[500px] border-2 border-gray-200 rounded-lg bg-gray-50"
      />

      {/* Selected node info */}
      {selectedNode && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-bold text-indigo-600 mb-2">Node Information</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <p><strong>ID:</strong> {selectedNode.id}</p>
            <p><strong>Name:</strong> {selectedNode.name}</p>
            <p><strong>Type:</strong> {selectedNode.type}</p>
            <p><strong>Connections:</strong> {selectedNode.connections}</p>
            {selectedNode.language && <p><strong>Language:</strong> {selectedNode.language}</p>}
            {selectedNode.file_path && <p className="col-span-2"><strong>File:</strong> {selectedNode.file_path}</p>}
            {selectedNode.line_start && <p><strong>Lines:</strong> {selectedNode.line_start}-{selectedNode.line_end || 'N/A'}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
