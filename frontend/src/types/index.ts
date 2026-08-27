// Shared TypeScript types that mirror backend Pydantic schemas.

export type AuthType = 'native_no_auth' | 'api_key' | 'oauth2' | 'credentialed';

export interface User {
  id: string;
  email: string;
  username: string;
  is_admin: boolean;
  composio_user_id: string;
  created_at: string;
}

export interface Connection {
  id?: string;
  user_id: string;
  toolkit_slug: string;
  composio_connected_account_id?: string;
  composio_auth_config_id?: string;
  status: string;
  connection_mode: 'native_no_auth' | 'connected_account';
  auth_type: AuthType;
  test_tool_slug?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ConnectionListResponse {
  connections: Connection[];
  total: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AdminUserRow {
  id: string;
  email: string;
  username: string;
  is_admin: boolean;
  composio_user_id: string;
  created_at: string;
  connection_count: number;
}

export interface AdminUserListResponse {
  users: AdminUserRow[];
  total: number;
}

export interface AdminConnectionDetail {
  id: string;
  user_id: string;
  toolkit_slug: string;
  composio_connected_account_id: string;
  composio_auth_config_id: string;
  connection_mode: 'native_no_auth' | 'connected_account';
  db_status: string;
  live_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserConnectionsResponse {
  user: User;
  connections: AdminConnectionDetail[];
  toolkits: ToolkitAuthInfo[];
}

export interface ToolkitAuthInfo {
  toolkit_slug: string;
  connection_required: boolean;
  connection_mode: 'native_no_auth' | 'connected_account';
  auth_type: AuthType;
  supported_auth_schemes: string[];
  test_tool_slug?: string;
  display_name?: string;
}

export interface ToolExecuteResponse {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export type ConnectionStatus =
  | 'ACTIVE'
  | 'INITIALIZING'
  | 'INITIATED'
  | 'FAILED'
  | 'EXPIRED'
  | 'INACTIVE'
  | 'REVOKED';
