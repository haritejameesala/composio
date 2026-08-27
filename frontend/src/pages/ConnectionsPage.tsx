import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import { AuthType, Connection, ToolkitAuthInfo } from '../types';
import { ConnectionCard } from '../components/ConnectionCard';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const ConnectionsPage: React.FC = () => {
  const { user } = useAuth();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [selectedToolkit, setSelectedToolkit] = useState('serpapi');
  const [toolkits, setToolkits] = useState<ToolkitAuthInfo[]>([]);
  const [credential, setCredential] = useState('');
  const [credentialDialogOpen, setCredentialDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const selectedToolkitInfo = toolkits.find((toolkit) => toolkit.toolkit_slug === selectedToolkit);
  const selectedUsesApiKey = selectedToolkitInfo?.auth_type === 'api_key'
    || selectedToolkitInfo?.supported_auth_schemes.some((scheme) => scheme.toUpperCase() === 'API_KEY');

  const fetchConnections = async () => {
    setError(null);
    try {
      const res = await api.get<{ connections: Connection[]; total: number }>('/api/connections');
      setConnections((current) => [
        ...res.data.connections,
        ...current.filter((item) => item.connection_mode === 'native_no_auth'),
      ]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load connections.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
    api.get<ToolkitAuthInfo[]>('/api/connections/toolkits')
      .then((res) => {
        setToolkits(res.data);
        const nativeToolkits = res.data
          .filter((item) => item.connection_mode === 'native_no_auth')
          .map((item) => ({
            user_id: user?.id || '',
            toolkit_slug: item.toolkit_slug,
            status: 'AVAILABLE_WITHOUT_CONNECTION',
            connection_mode: item.connection_mode,
            auth_type: item.auth_type as AuthType,
            test_tool_slug: item.test_tool_slug,
          }));
        setConnections((current) => [
          ...nativeToolkits,
          ...current.filter((item) => !nativeToolkits.some((native) => native.toolkit_slug === item.toolkit_slug)),
        ]);
        nativeToolkits.forEach((toolkit) => {
          api.get<{ test_tool_slug?: string }>(`/api/connections/toolkits/${toolkit.toolkit_slug}/test-tool`)
            .then((toolRes) => {
              setConnections((current) => current.map((item) => item.toolkit_slug === toolkit.toolkit_slug
                ? { ...item, test_tool_slug: toolRes.data.test_tool_slug }
                : item));
            });
        });
        if (res.data.length > 0 && !res.data.some((item) => item.toolkit_slug === selectedToolkit)) {
          setSelectedToolkit(res.data[0].toolkit_slug);
        }
      })
      .catch((err) => setError(err.response?.data?.detail || 'Failed to discover toolkits.'));
  }, []);

  const handleAddComposio = async () => {
    setProvisioning(true);
    setError(null);
    setSuccessMessage(null);

    try {
      if (selectedToolkitInfo?.auth_type === 'oauth2') {
        const oauth = await api.post<{ redirect_url: string }>('/api/connections/oauth', {
          toolkit_slug: selectedToolkit,
        });
        window.location.assign(oauth.data.redirect_url);
        return;
      }
      const res = await api.post<Connection>('/api/connections', {
        toolkit_slug: selectedToolkit,
        credentials: credential ? { api_key: credential } : undefined,
      });

      setSuccessMessage(
        res.data.connection_mode === 'native_no_auth'
          ? `${res.data.toolkit_slug.toUpperCase()} is available without connection.`
          : `Successfully connected Composio toolkit "${res.data.toolkit_slug.toUpperCase()}"! Account status is ${res.data.status}.`
      );
      if (res.data.connection_mode === 'native_no_auth') {
        setConnections((current) => [
          ...current.filter((item) => item.toolkit_slug !== res.data.toolkit_slug),
          res.data,
        ]);
      } else {
        setCredential('');
        setCredentialDialogOpen(false);
        await fetchConnections();
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Failed to provision connection';
      setError(`Provisioning error: ${detail}`);
      setCredential('');
      setCredentialDialogOpen(false);
    } finally {
      setProvisioning(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="md:flex md:items-center md:justify-between pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">Composio Connections</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage your connected third-party toolkits. All connections are authenticated securely via backend Composio API.
          </p>
        </div>
        <div className="mt-4 md:mt-0 flex items-center space-x-3">
          <button
            onClick={() => {
              setLoading(true);
              fetchConnections();
            }}
            disabled={loading}
            className="px-3.5 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-sm"
          >
            Refresh Status
          </button>
        </div>
      </div>

      {/* Identity Summary Card */}
      <div className="mt-6 bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-xl p-5 shadow-sm">
        <div className="sm:flex sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-indigo-900 uppercase tracking-wider">
              Stable User Mapping
            </h2>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-500 font-medium">Internal User ID:</span>
                <p className="font-mono text-slate-800 bg-white/70 px-2 py-1 rounded border border-indigo-100 mt-0.5 select-all">
                  {user?.id}
                </p>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Composio User ID:</span>
                <p className="font-mono text-indigo-900 font-semibold bg-white/70 px-2 py-1 rounded border border-indigo-100 mt-0.5 select-all">
                  {user?.composio_user_id}
                </p>
              </div>
            </div>
          </div>
          <div className="mt-4 sm:mt-0 text-right sm:border-l sm:border-indigo-100 sm:pl-6">
            <span className="text-xs text-indigo-700 font-medium">Authentication</span>
            <p className="text-sm font-bold text-indigo-950 mt-0.5">Backend Managed</p>
            <p className="text-[11px] text-indigo-600">Backend connection secure</p>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mt-6 bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3.5 rounded-xl text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {successMessage && (
        <div className="mt-6 bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3.5 rounded-xl text-sm flex items-center justify-between">
          <span>{successMessage}</span>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-600 hover:text-emerald-800 font-bold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Add Composio Section */}
      <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Add Composio Toolkit</h2>
        <p className="text-xs text-slate-500 mt-1">
          Select a toolkit. Native toolkits are available without a connected account; credentialed toolkits require authorization.
        </p>

        <div className="mt-4 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="flex-1 max-w-xs">
            <label htmlFor="toolkit-select" className="sr-only">
              Select Toolkit
            </label>
            <select
              id="toolkit-select"
              value={selectedToolkit}
              onChange={(e) => setSelectedToolkit(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 bg-white py-2.5 px-3 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500 text-sm font-medium text-slate-700"
            >
              {toolkits.map((toolkit) => (
                <option key={toolkit.toolkit_slug} value={toolkit.toolkit_slug}>
                  {toolkit.toolkit_slug.toUpperCase()} ({toolkit.connection_mode === 'native_no_auth' ? 'No connection required' : toolkit.supported_auth_schemes.join(', ')})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => selectedUsesApiKey ? setCredentialDialogOpen(true) : handleAddComposio()}
            disabled={provisioning}
            className="inline-flex items-center justify-center px-5 py-2.5 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition"
          >
            {provisioning ? (
              <>
                <span className="w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                Provisioning with Composio...
              </>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                {selectedToolkitInfo?.auth_type === 'oauth2'
                  ? `Connect with ${selectedToolkitInfo.display_name || selectedToolkit}`
                  : selectedToolkitInfo?.auth_type === 'native_no_auth'
                    ? 'Make Available'
                    : 'Connect with API key'}
              </>
            )}
          </button>
        </div>
      </div>

      {credentialDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div role="dialog" aria-modal="true" aria-labelledby="credential-dialog-title" className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 id="credential-dialog-title" className="text-lg font-semibold text-slate-900">
              Enter your {selectedToolkitInfo?.display_name || selectedToolkit} API key
            </h2>
            <form onSubmit={(event) => { event.preventDefault(); handleAddComposio(); }} className="mt-4">
              <input
                autoFocus
                type="password"
                value={credential}
                onChange={(event) => setCredential(event.target.value)}
                autoComplete="off"
                className="block w-full rounded-lg border border-slate-300 bg-white py-2.5 px-3 text-sm text-slate-700"
              />
              <div className="mt-5 flex justify-end gap-3">
                <button type="button" onClick={() => { setCredential(''); setCredentialDialogOpen(false); }} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700">
                  Cancel
                </button>
                <button type="submit" disabled={!credential || provisioning} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                  {provisioning ? 'Connecting...' : 'Connect'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Connection List */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Available Toolkits and Connections ({connections.length})</h2>

        {loading ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
            <LoadingSpinner size="lg" text="Loading your Composio connections..." />
          </div>
        ) : connections.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-slate-300 p-12 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400 mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-slate-900">No Composio connections yet</h3>
            <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
              Native toolkits appear as available without connection after selection.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {connections.map((conn) => (
              <ConnectionCard key={conn.id || `native-${conn.toolkit_slug}`} connection={conn} onDeleted={fetchConnections} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

