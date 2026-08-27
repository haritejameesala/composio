import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center space-x-6">
            <Link to="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                C
              </div>
              <span className="font-bold text-xl text-slate-800 tracking-tight">Composio Hub</span>
            </Link>

            {user && (
              <nav className="flex space-x-4">
                <Link
                  to="/connections"
                  className="text-slate-600 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium transition-colors"
                >
                  Connections
                </Link>
                {user.is_admin && (
                  <Link
                    to="/admin"
                    className="text-amber-600 hover:text-amber-700 px-3 py-2 rounded-md text-sm font-medium bg-amber-50 border border-amber-200 transition-colors"
                  >
                    Admin Dashboard
                  </Link>
                )}
              </nav>
            )}
          </div>

          <div className="flex items-center space-x-4">
            {user ? (
              <div className="flex items-center space-x-4">
                <div className="text-right hidden sm:block">
                  <div className="text-sm font-semibold text-slate-800 flex items-center gap-1.5 justify-end">
                    {user.username}
                    {user.is_admin && (
                      <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-1.5 py-0.5 rounded uppercase">
                        Admin
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 font-mono" title={`Composio ID: ${user.composio_user_id}`}>
                    Composio: {user.composio_user_id.slice(0, 8)}...
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="text-slate-600 hover:text-rose-600 px-3 py-1.5 rounded-md text-sm font-medium border border-slate-200 hover:border-rose-200 hover:bg-rose-50 transition"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-3">
                <Link
                  to="/login"
                  className="text-slate-600 hover:text-slate-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md text-sm font-medium shadow-sm transition"
                >
                  Sign up
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

