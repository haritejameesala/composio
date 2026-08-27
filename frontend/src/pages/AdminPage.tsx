import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { AdminUserRow, AdminConnectionDetail, ToolkitAuthInfo, User } from '../types';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const AdminPage: React.FC = () => {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  
  // Selected user connection details
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [connections, setConnections] = useState<AdminConnectionDetail[]>([]);
  const [toolkits, setToolkits] = useState<ToolkitAuthInfo[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async (searchQuery = '') => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ users: AdminUserRow[]; total: number }>('/api/admin/users', {
        params: { search: searchQuery || undefined },
      });
      setUsers(res.data.users);
      if (res.data.users.length > 0 && !selectedUserId) {
        setSelectedUserId(res.data.users[0].id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load user directory.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUserConnections = async (userId: string) => {
    setLoadingConnections(true);
    setError(null);
    try {
      const res = await api.get<{ user: User; connections: AdminConnectionDetail[]; toolkits: ToolkitAuthInfo[] }>(
        `/api/admin/users/${userId}/connections`
      );
      setSelectedUser(res.data.user);
      setConnections(res.data.connections);
      setToolkits(res.data.toolkits || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load user connections.');
    } finally {
      setLoadingConnections(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (selectedUserId) {
      fetchUserConnections(selectedUserId);
    }
  }, [selectedUserId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchUsers(search);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="pb-6 border-b border-slate-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 uppercase tracking-wider">
                Admin Area
              </span>
              <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">Composio Admin Inspector</h1>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Inspect user Composio identities, auth configs, connected account IDs, and live status from Composio.
            </p>
          </div>
          <a
            href="https://dashboard.composio.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition"
          >
            Open Composio Dashboard ↗
          </a>
        </div>
      </div>

      {error && (
        <div className="mt-6 bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Main Grid: User List (Left) + Detail View (Right) */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* User Search & List */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <form onSubmit={handleSearchSubmit} className="flex gap-2">
              <input
                type="text"
                placeholder="Search username or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition"
              >
                Search
              </button>
            </form>

            <div className="mt-4 divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
              {loading ? (
                <div className="py-8">
                  <LoadingSpinner size="md" text="Loading users..." />
                </div>
              ) : users.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-500">No users found.</div>
              ) : (
                users.map((u) => (
                  <button
                    key={u.id}
                    onClick={() => setSelectedUserId(u.id)}
                    className={`w-full text-left p-3.5 rounded-lg transition flex flex-col space-y-1 ${
                      selectedUserId === u.id
                        ? 'bg-indigo-50 border border-indigo-200'
                        : 'hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-sm text-slate-900 flex items-center gap-1.5">
                        {u.username}
                        {u.is_admin && (
                          <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.2 rounded font-bold uppercase">
                            Admin
                          </span>
                        )}
                      </span>
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">
                        {u.connection_count} conn{u.connection_count === 1 ? '' : 's'}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">{u.email}</span>
                    <span className="text-[11px] font-mono text-slate-400 truncate" title={u.composio_user_id}>
                      Composio ID: {u.composio_user_id}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Selected User Details */}
        <div className="lg:col-span-7">
          {loadingConnections ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
              <LoadingSpinner size="lg" text="Fetching live Composio connection details..." />
            </div>
          ) : selectedUser ? (
            <div className="space-y-6">
              {/* User Identity Box */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                  <h2 className="text-lg font-semibold text-slate-900">User Identity Mapping</h2>
                  <button
                    onClick={() => fetchUserConnections(selectedUser.id)}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 underline"
                  >
                    Sync Live Status
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500 font-medium">Platform User ID (Internal):</span>
                    <div className="mt-1 font-mono text-slate-900 bg-slate-50 p-2 rounded border border-slate-200 select-all break-all">
                      {selectedUser.id}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-500 font-medium">Composio User ID:</span>
                    <div className="mt-1 font-mono text-indigo-900 font-semibold bg-indigo-50/70 p-2 rounded border border-indigo-200 select-all break-all">
                      {selectedUser.composio_user_id}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-500 font-medium">Email:</span>
                    <div className="mt-1 text-slate-800 bg-slate-50 p-2 rounded border border-slate-200 truncate">
                      {selectedUser.email}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-500 font-medium">Created:</span>
                    <div className="mt-1 text-slate-800 bg-slate-50 p-2 rounded border border-slate-200">
                      {new Date(selectedUser.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Connections Box */}
              {toolkits.length > 0 && (
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900 mb-4">Toolkit Auth Modes</h2>
                  <div className="space-y-2">
                    {toolkits.map((toolkit) => (
                      <div key={toolkit.toolkit_slug} className="flex items-center justify-between text-sm">
                        <span className="font-semibold text-slate-900 uppercase">{toolkit.toolkit_slug}</span>
                        <span className="text-xs font-medium text-slate-600">
                          {toolkit.connection_required ? `Connected account (${toolkit.supported_auth_schemes.join(', ')})` : 'Available without connection'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Connections Box */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  Provisioned Connections ({connections.length})
                </h2>

                {connections.length === 0 ? (
                  <div className="text-center py-8 text-sm text-slate-500 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                    This user has not provisioned any Composio toolkits.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {connections.map((c) => (
                      <div
                        key={c.id}
                        className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 hover:bg-white transition"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sm text-slate-900 uppercase tracking-wide">
                            {c.toolkit_slug}
                          </span>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-slate-500 font-medium">Status:</span>
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                c.db_status === 'ACTIVE'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {c.db_status}
                            </span>
                            {c.live_status && (
                              <span className="text-[11px] text-slate-400">
                                (Live: {c.live_status})
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                          <div>
                            <span className="text-slate-500">Connected Account ID:</span>
                            <p className="font-mono text-slate-800 bg-white p-1.5 rounded border border-slate-200 mt-0.5 select-all truncate" title={c.composio_connected_account_id}>
                              {c.composio_connected_account_id}
                            </p>
                          </div>
                          <div>
                            <span className="text-slate-500">Auth Config ID:</span>
                            <p className="font-mono text-slate-800 bg-white p-1.5 rounded border border-slate-200 mt-0.5 select-all truncate" title={c.composio_auth_config_id}>
                              {c.composio_auth_config_id || 'Cached in DB'}
                            </p>
                          </div>
                        </div>

                        <div className="mt-2 text-[11px] text-slate-400">
                          Provisioned on: {new Date(c.created_at).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-sm text-slate-500 shadow-sm">
              Select a user from the directory to inspect their Composio mapping.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

