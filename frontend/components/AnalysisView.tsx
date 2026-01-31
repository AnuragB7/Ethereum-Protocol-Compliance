'use client';

import React, { useState } from 'react';
import { Search, Loader } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  analyzeFunction,
  generateTests,
  generateSeleniumTests,
  generateUnitTests,
  getCallChain,
} from '../lib/api';

export default function AnalysisView() {
  const [functionName, setFunctionName] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [testCases, setTestCases] = useState<any>(null);
  const [seleniumCode, setSeleniumCode] = useState('');
  const [unitTestCode, setUnitTestCode] = useState('');
  const [callChains, setCallChains] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'analysis' | 'tests' | 'selenium' | 'unit' | 'callchain'>('analysis');

  const handleAnalyze = async () => {
    if (!functionName.trim()) return;

    setLoading(true);
    try {
      const [analysisResult, testResult, seleniumResult, unitResult, chainResult] = await Promise.all([
        analyzeFunction(functionName),
        generateTests(functionName, 5),
        generateSeleniumTests(functionName),
        generateUnitTests(functionName),
        getCallChain(functionName, 3),
      ]);

      setAnalysis(analysisResult);
      setTestCases(testResult);
      setSeleniumCode(seleniumResult.selenium_code);
      setUnitTestCode(unitResult.unit_test_code);
      setCallChains(chainResult);
    } catch (error: any) {
      console.error('Analysis failed:', error);
      alert(error.response?.data?.detail || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Code Analysis</h2>

      <div className="mb-6 flex gap-4">
        <div className="flex-1 relative">
          <input
            type="text"
            value={functionName}
            onChange={(e) => setFunctionName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleAnalyze()}
            placeholder="Enter function/method name to analyze..."
            className="w-full px-4 py-3 pl-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <Search className="absolute left-4 top-3.5 text-gray-400" size={20} />
        </div>
        <button
          onClick={handleAnalyze}
          disabled={loading || !functionName.trim()}
          className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400 flex items-center gap-2"
        >
          {loading ? (
            <>
              <Loader className="animate-spin" size={20} />
              Analyzing...
            </>
          ) : (
            'Analyze'
          )}
        </button>
      </div>

      {analysis && (
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="flex border-b border-gray-200">
            {[
              { key: 'analysis', label: 'Functional Analysis' },
              { key: 'tests', label: 'Test Cases' },
              { key: 'selenium', label: 'Selenium Tests' },
              { key: 'unit', label: 'Unit Tests' },
              { key: 'callchain', label: 'Call Chains' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`px-6 py-3 font-medium transition ${
                  activeTab === tab.key
                    ? 'border-b-2 border-primary-600 text-primary-600'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {activeTab === 'analysis' && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xl font-semibold mb-2">Function: {analysis.function_name}</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    {analysis.entity.language} • {analysis.entity.type} • {analysis.entity.file_path}
                  </p>
                </div>
                <div className="prose max-w-none">
                  <pre className="whitespace-pre-wrap bg-gray-50 p-4 rounded-lg">
                    {analysis.analysis}
                  </pre>
                </div>
              </div>
            )}

            {activeTab === 'tests' && testCases && (
              <div className="space-y-4">
                <h3 className="text-xl font-semibold">Top 5 Test Cases</h3>
                <div className="prose max-w-none">
                  <pre className="whitespace-pre-wrap bg-gray-50 p-4 rounded-lg">
                    {testCases.test_cases}
                  </pre>
                </div>
              </div>
            )}

            {activeTab === 'selenium' && seleniumCode && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-xl font-semibold">Selenium Test Code</h3>
                  <button
                    onClick={() => copyToClipboard(seleniumCode)}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
                  >
                    Copy Code
                  </button>
                </div>
                <SyntaxHighlighter language="python" style={vscDarkPlus} className="rounded-lg">
                  {seleniumCode}
                </SyntaxHighlighter>
              </div>
            )}

            {activeTab === 'unit' && unitTestCode && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-xl font-semibold">Unit Test Code</h3>
                  <button
                    onClick={() => copyToClipboard(unitTestCode)}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
                  >
                    Copy Code
                  </button>
                </div>
                <SyntaxHighlighter language="python" style={vscDarkPlus} className="rounded-lg">
                  {unitTestCode}
                </SyntaxHighlighter>
              </div>
            )}

            {activeTab === 'callchain' && callChains && (
              <div className="space-y-4">
                <h3 className="text-xl font-semibold">
                  Call Chains ({callChains.chain_count} paths found)
                </h3>
                <div className="space-y-2">
                  {callChains.chains.slice(0, 20).map((chain: string[], idx: number) => (
                    <div key={idx} className="bg-gray-50 p-3 rounded-lg font-mono text-sm">
                      {chain.join(' → ')}
                    </div>
                  ))}
                  {callChains.chains.length > 20 && (
                    <p className="text-gray-600 text-sm">
                      ... and {callChains.chains.length - 20} more chains
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
