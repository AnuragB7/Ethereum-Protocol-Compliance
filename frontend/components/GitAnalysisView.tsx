'use client';

import React, { useState } from 'react';
import { 
  GitBranch, 
  Copy,
  Check,
  Settings,
  Zap,
  Clock,
  Info,
  ExternalLink
} from 'lucide-react';

// CI Configuration types
interface CIConfig {
  mode: 'quick' | 'deep';
  failOnCritical: boolean;
  failOnWarning: boolean;
}

// Generate GitHub Actions workflow YAML
const generateWorkflowYAML = (config: CIConfig): string => {
  return `name: PR Compliance Analysis

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  analyze:
    name: Analyze PR for Compliance
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    
    steps:
      - name: Run Compliance Analysis
        id: analysis
        run: |
          RESPONSE=$(curl -s -X POST "\${{ secrets.COMPLIANCE_API_URL }}/api/pr-analysis/ci" \\
            -H "Content-Type: application/json" \\
            -H "Authorization: Bearer \${{ secrets.GITHUB_TOKEN }}" \\
            -d '{
              "owner": "\${{ github.repository_owner }}",
              "repo": "\${{ github.event.repository.name }}",
              "pr_number": \${{ github.event.pull_request.number }},
              "mode": "${config.mode}",
              "fail_on_critical": ${config.failOnCritical},
              "fail_on_warning": ${config.failOnWarning}
            }')
          
          echo "response<<EOF" >> $GITHUB_OUTPUT
          echo "$RESPONSE" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
          
          # Extract fields for conditional steps
          HAS_ISSUES=$(echo "$RESPONSE" | jq -r '.has_issues // false')
          SHOULD_FAIL=$(echo "$RESPONSE" | jq -r '.should_fail // false')
          echo "has_issues=$HAS_ISSUES" >> $GITHUB_OUTPUT
          echo "should_fail=$SHOULD_FAIL" >> $GITHUB_OUTPUT
          
          # Save markdown comment to file (handles multiline better)
          echo "$RESPONSE" | jq -r '.markdown_comment // ""' > comment.md

      - name: Post PR Comment
        if: steps.analysis.outputs.has_issues == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const comment = fs.readFileSync('comment.md', 'utf8');
            if (comment.trim()) {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: comment
              });
            }

      - name: Check Compliance Status
        if: steps.analysis.outputs.should_fail == 'true'
        run: |
          echo "Compliance check failed. See PR comment for details."
          exit 1
`;
};

export default function GitAnalysisView() {
  // CI Configuration state
  const [ciConfig, setCiConfig] = useState<CIConfig>({
    mode: 'quick',
    failOnCritical: true,
    failOnWarning: false
  });
  const [workflowGenerated, setWorkflowGenerated] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyWorkflow = async () => {
    const yaml = generateWorkflowYAML(ciConfig);
    try {
      await navigator.clipboard.writeText(yaml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl">
          <GitBranch size={28} className="text-white" />
        </div>
        <div>
          <h2 className="text-3xl font-bold text-gray-800">Automated CI/CD Compliance</h2>
          <p className="text-gray-600">Set up GitHub Actions to automatically analyze PRs for Ethereum compliance</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* How It Works */}
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-purple-600" />
            How It Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg border border-purple-100">
              <div className="w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold text-lg">1</div>
              <p className="text-sm font-medium text-gray-800">PR Opened</p>
              <p className="text-xs text-gray-500 mt-1">Developer creates PR on GitHub</p>
            </div>
            <div className="text-center p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg border border-purple-100">
              <div className="w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold text-lg">2</div>
              <p className="text-sm font-medium text-gray-800">Workflow Triggers</p>
              <p className="text-xs text-gray-500 mt-1">GitHub Actions automatically runs</p>
            </div>
            <div className="text-center p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg border border-purple-100">
              <div className="w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold text-lg">3</div>
              <p className="text-sm font-medium text-gray-800">LLM Analyzes</p>
              <p className="text-xs text-gray-500 mt-1">Your API checks compliance</p>
            </div>
            <div className="text-center p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg border border-purple-100">
              <div className="w-10 h-10 bg-purple-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold text-lg">4</div>
              <p className="text-sm font-medium text-gray-800">Comment Posted</p>
              <p className="text-xs text-gray-500 mt-1">Results appear on PR (if issues)</p>
            </div>
          </div>
        </div>

        {/* GitHub Secret Setup Guide */}
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Info className="w-5 h-5 text-blue-600" />
            Required GitHub Secret Configuration
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            The workflow uses a secret to know where your Compliance API is deployed. Add this secret to your GitHub repository:
          </p>
          
          {/* Visual representation of GitHub Secrets UI */}
          <div className="bg-gray-900 rounded-lg overflow-hidden border border-gray-700">
            {/* Fake GitHub header */}
            <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>
              <span className="text-gray-400 text-xs ml-2">Settings → Secrets and variables → Actions → New repository secret</span>
            </div>
            
            {/* Secret form mockup */}
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Name *</label>
                <div className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-green-400 font-mono text-sm">
                  COMPLIANCE_API_URL
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Secret *</label>
                <div className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-green-400 font-mono text-sm">
                  https://your-deployed-backend.com
                </div>
                <p className="text-xs text-gray-500 mt-1.5">
                  ↑ Replace with your actual deployed backend URL
                </p>
              </div>
              <div className="pt-2">
                <div className="inline-block bg-green-600 text-white px-4 py-1.5 rounded text-sm font-medium">
                  Add secret
                </div>
              </div>
            </div>
          </div>
          
          <p className="text-xs text-gray-500 mt-3">
            Navigate to: <span className="font-medium">Your Repository → Settings → Secrets and variables → Actions → New repository secret</span>
          </p>
        </div>

        {/* Configuration Form */}
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Configure Your Workflow</h3>
          
          <div className="space-y-5">
            {/* Analysis Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Analysis Mode
              </label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setCiConfig({ ...ciConfig, mode: 'quick' })}
                  className={`p-4 rounded-xl border-2 text-left transition ${
                    ciConfig.mode === 'quick'
                      ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-200'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className={`w-5 h-5 ${ciConfig.mode === 'quick' ? 'text-purple-600' : 'text-gray-400'}`} />
                    <span className="font-semibold text-gray-800">Quick Mode</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Diff-based analysis using GitHub API. Fast feedback in ~30 seconds.
                  </p>
                  <p className="text-xs text-purple-600 mt-2 font-medium">Recommended for most PRs</p>
                </button>
                <button
                  onClick={() => setCiConfig({ ...ciConfig, mode: 'deep' })}
                  className={`p-4 rounded-xl border-2 text-left transition ${
                    ciConfig.mode === 'deep'
                      ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-200'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className={`w-5 h-5 ${ciConfig.mode === 'deep' ? 'text-purple-600' : 'text-gray-400'}`} />
                    <span className="font-semibold text-gray-800">Deep Mode</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Clones repo and builds full property graph. Takes 2-5 minutes.
                  </p>
                  <p className="text-xs text-gray-500 mt-2">Best for critical/release PRs</p>
                </button>
              </div>
            </div>

            {/* Failure Thresholds */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                When Should CI Fail?
              </label>
              <div className="space-y-3">
                <label className="flex items-start gap-3 p-3 rounded-lg border-2 border-gray-200 hover:border-gray-300 cursor-pointer transition">
                  <input
                    type="checkbox"
                    checked={ciConfig.failOnCritical}
                    onChange={(e) => setCiConfig({ ...ciConfig, failOnCritical: e.target.checked })}
                    className="w-5 h-5 text-purple-600 rounded focus:ring-purple-500 mt-0.5"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-800">Fail on Critical Issues</span>
                    <p className="text-xs text-gray-500 mt-0.5">Block PR merge when critical compliance violations are found</p>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 rounded-lg border-2 border-gray-200 hover:border-gray-300 cursor-pointer transition">
                  <input
                    type="checkbox"
                    checked={ciConfig.failOnWarning}
                    onChange={(e) => setCiConfig({ ...ciConfig, failOnWarning: e.target.checked })}
                    className="w-5 h-5 text-purple-600 rounded focus:ring-purple-500 mt-0.5"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-800">Fail on Warnings</span>
                    <p className="text-xs text-gray-500 mt-0.5">Also block PR merge for warning-level issues (stricter)</p>
                  </div>
                </label>
              </div>
            </div>

            {/* Generate Button */}
            <button
              onClick={() => setWorkflowGenerated(true)}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 transition font-semibold text-lg"
            >
              Generate GitHub Actions Workflow
            </button>
          </div>
        </div>

        {/* Generated Workflow */}
        {workflowGenerated && (
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <code className="text-sm text-gray-300">.github/workflows/pr-compliance.yml</code>
              </div>
              <button
                onClick={handleCopyWorkflow}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  copied
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                }`}
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy to Clipboard
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 overflow-x-auto text-sm bg-gray-900 text-gray-100 max-h-96">
              <code>{generateWorkflowYAML(ciConfig)}</code>
            </pre>
          </div>
        )}

        {/* Setup Instructions */}
        {workflowGenerated && (
          <div className="bg-blue-50 rounded-xl p-5 border border-blue-200">
            <div className="flex items-start gap-3">
              <Info className="w-6 h-6 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-blue-800 mb-3 text-lg">Setup Instructions</p>
                <ol className="list-decimal list-inside space-y-2 text-blue-700">
                  <li>Copy the workflow YAML above</li>
                  <li>In your GitHub repository, create the file: <code className="bg-blue-100 px-1.5 py-0.5 rounded">.github/workflows/pr-compliance.yml</code></li>
                  <li>Paste the workflow content and commit to your main branch</li>
                  <li>Go to your repo's <strong>Settings → Secrets and variables → Actions</strong></li>
                  <li>Click <strong>"New repository secret"</strong></li>
                  <li>
                    Add secret with name: <code className="bg-blue-100 px-1.5 py-0.5 rounded">COMPLIANCE_API_URL</code>
                    <br />
                    <span className="text-sm">Value: Your deployed backend URL (e.g., <code className="bg-blue-100 px-1.5 py-0.5 rounded">https://your-compliance-api.com</code>)</span>
                  </li>
                  <li>Open a test PR to verify the integration works</li>
                </ol>
                <div className="mt-4 p-3 bg-blue-100 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>Note:</strong> Comments are only posted when compliance issues are found. 
                    Clean PRs pass silently with a green checkmark.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Link to Manual Analysis */}
        <div className="bg-gray-50 rounded-xl p-4 border">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-700">Want to analyze a PR manually?</p>
              <p className="text-sm text-gray-500">Use the Manual PR Compliance tab to analyze specific PRs on-demand</p>
            </div>
            <button
              onClick={() => {
                window.dispatchEvent(new CustomEvent('navigate', { detail: 'llm-compliance-analysis' }));
              }}
              className="flex items-center gap-2 px-4 py-2 bg-white border rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm font-medium"
            >
              Go to Manual Analysis
              <ExternalLink className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
