'use client';

import React, { useState } from 'react';
import { Upload, Folder, Check, AlertCircle, Trash2, GitBranch } from 'lucide-react';
import { uploadCodebase, uploadFolder, uploadFolderIncremental, resetGraph } from '../lib/api';

interface UploadStepProps {
  onUploadSuccess: (data: any) => void;
}

export default function UploadStep({ onUploadSuccess }: UploadStepProps) {
  const [uploadMode, setUploadMode] = useState<'file' | 'folder'>('file');
  const [folderPath, setFolderPath] = useState('');
  const [incremental, setIncremental] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.zip')) {
      setError('Please upload a ZIP file');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const result = await uploadCodebase(file);
      setSuccess('Codebase uploaded and indexed successfully!');
      onUploadSuccess(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleFolderUpload = async () => {
    if (!folderPath.trim()) {
      setError('Please enter a folder path');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const result = incremental
        ? await uploadFolderIncremental(folderPath)
        : await uploadFolder(folderPath);

      // Build a descriptive success message
      if (result.skipped) {
        setSuccess('✅ Codebase unchanged — no re-indexing needed (Merkle root identical).');
      } else if (result.incremental) {
        const a = result.added_files ?? 0;
        const m = result.modified_files ?? 0;
        const d = result.deleted_files ?? 0;
        setSuccess(
          `⚡ Incremental ingestion complete: ${a} added, ${m} modified, ${d} deleted. ` +
          `Graph now has ${result.entities_extracted} entities.`
        );
      } else {
        setSuccess('Codebase indexed successfully!');
      }
      onUploadSuccess(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Indexing failed');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset? This will clear all indexed code and compliance data.')) {
      return;
    }

    setResetting(true);
    setError('');
    setSuccess('');

    try {
      const result = await resetGraph();
      setSuccess(`Graph reset successfully! Cleared ${result.details?.entities_cleared || 0} entities and ${result.details?.relationships_cleared || 0} relationships.`);
      setFolderPath('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Reset failed');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Upload Codebase</h2>
        <button
          onClick={handleReset}
          disabled={resetting || uploading}
          className="flex items-center gap-2 px-4 py-2 text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
          title="Reset graph and start fresh"
        >
          <Trash2 size={18} />
          {resetting ? 'Resetting...' : 'Reset Graph'}
        </button>
      </div>

      {/* Mode selector */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setUploadMode('file')}
          className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition ${
            uploadMode === 'file'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          <Upload size={20} />
          Upload ZIP File
        </button>
        <button
          onClick={() => setUploadMode('folder')}
          className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition ${
            uploadMode === 'folder'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          <Folder size={20} />
          Local Folder
        </button>
      </div>

      {/* Upload interface */}
      {uploadMode === 'file' ? (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <Upload className="mx-auto mb-4 text-gray-400" size={48} />
          <p className="mb-4 text-gray-600">
            Upload a ZIP file containing your codebase
          </p>
          <label className="cursor-pointer inline-block px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition">
            <input
              type="file"
              accept=".zip"
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
            {uploading ? 'Uploading...' : 'Select ZIP File'}
          </label>
          <p className="mt-4 text-sm text-gray-500">
            Supports Python (.py), Java (.java), and COBOL (.cob, .cbl)
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Folder Path
            </label>
            <input
              type="text"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder="/path/to/your/codebase"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              disabled={uploading}
            />
          </div>

          {/* Incremental toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2">
              <GitBranch size={18} className="text-primary-600" />
              <div>
                <span className="text-sm font-medium text-gray-800">Incremental Ingestion (Merkle Tree)</span>
                <p className="text-xs text-gray-500">Only re-parse changed files — skips unchanged code</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIncremental(!incremental)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                incremental ? 'bg-primary-600' : 'bg-gray-300'
              }`}
              disabled={uploading}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  incremental ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <button
            onClick={handleFolderUpload}
            disabled={uploading}
            className="w-full py-3 px-4 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400"
          >
            {uploading
              ? 'Processing...'
              : incremental
              ? 'Index Codebase (Incremental)'
              : 'Index Codebase (Full)'
            }
          </button>
        </div>
      )}

      {/* Status messages */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {success && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-2">
          <Check className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
          <p className="text-green-700">{success}</p>
        </div>
      )}

      {uploading && (
        <div className="mt-4">
          <div className="animate-pulse flex space-x-4">
            <div className="flex-1 space-y-3">
              <div className="h-2 bg-primary-200 rounded"></div>
              <div className="h-2 bg-primary-200 rounded w-5/6"></div>
            </div>
          </div>
          <p className="text-center text-sm text-gray-600 mt-2">
            Processing codebase... This may take a few minutes.
          </p>
        </div>
      )}
    </div>
  );
}

