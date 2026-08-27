import React, { useState } from 'react';
import { Connection } from '../types';
import api from '../api/client';

interface ConnectionCardProps {
  connection: Connection;
  onDeleted: () => void;
}

export const ConnectionCard: React.FC<ConnectionCardProps> = ({ connection, onDeleted }) => {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-500"></span>
            ACTIVE
          </span>
        );
      case 'INITIALIZING':
      case 'INITIATED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-blue-500 animate-pulse"></span>
            {status}
          </span>
        );
      case 'FAILED':
      case 'EXPIRED':
      case 'REVOKED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-rose-500"></span>
            {status}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800">
            {status}
          </span>
        );
    }
  };

  const handleTestExecution = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      if (!connection.test_tool_slug) {
        setTestResult({ success: false, message: 'No test tool available' });
        return;
      }
      const res = await api.post('/api/tools/execute', {
        tool_slug: connection.test_tool_slug,
        arguments: {},
      });
      setTestResult({
        success: true,
        message: `Execution succeeded! Result received from Composio. Data keys: ${Object.keys(res.data.data || {}).join(', ')}`,
      });
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Execution failed';
      setTestResult({
        success: false,
        message: `Execution failed: ${msg}`,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!connection.id) return;
    if (!window.confirm(`Delete connection for ${connection.toolkit_slug}?`)) return;
    setDeleting(true);
    try {
      await api.delete(`/api/connections/${connection.id}`);
      onDeleted();
    } catch (err: any) {
      alert(`Failed to delete connection: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-lg uppercase">
            {connection.toolkit_slug.slice(0, 2)}
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900 uppercase tracking-wide">
              {connection.toolkit_slug}
            </h3>
            <p className="text-xs text-slate-500">
              {connection.connection_mode === 'native_no_auth' ? 'No connection required' : 'Connected account'}
            </p>
          </div>
        </div>
        <div>{getStatusBadge(connection.status)}</div>
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100 space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-slate-500">Connected Account ID:</span>
            <span className="font-mono text-slate-700 select-all" title={connection.composio_connected_account_id}>
            {connection.composio_connected_account_id?.slice(0, 16) || 'None'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Auth Config ID:</span>
            <span className="font-mono text-slate-700 select-all" title={connection.composio_auth_config_id}>
            {connection.composio_auth_config_id ? `${connection.composio_auth_config_id.slice(0, 16)}...` : 'None'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Provisioned:</span>
            <span className="text-slate-700">{connection.created_at ? new Date(connection.created_at).toLocaleString() : 'Not provisioned'}</span>
        </div>
      </div>

      {testResult && (
        <div
          className={`mt-4 p-3 rounded-lg text-xs leading-relaxed ${
            testResult.success
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          {testResult.message}
        </div>
      )}

      <div className="mt-5 flex items-center justify-between pt-3 border-t border-slate-100">
        <button
          onClick={handleTestExecution}
          disabled={testing}
          className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition disabled:opacity-50"
        >
          {testing ? 'Testing Tool...' : connection.test_tool_slug ? `Test ${connection.test_tool_slug}` : 'No test tool available'}
        </button>

        {connection.id && <button
          onClick={handleDelete}
          disabled={deleting}
          className="text-xs font-medium text-slate-400 hover:text-rose-600 transition disabled:opacity-50"
        >
          {deleting ? 'Deleting...' : 'Disconnect'}
        </button>}
      </div>
    </div>
  );
};

