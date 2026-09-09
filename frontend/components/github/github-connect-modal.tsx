'use client';

import { useState } from 'react';
import {
  Shield,
  Check,
  X,
  ExternalLink,
  Key,
  Globe,
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
  Copy,
  CheckCheck,
} from 'lucide-react';
import { connectGitHub, connectGitHubToken, ApiClientError } from '@/lib/api';

interface GitHubConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  oauthConfigured?: boolean;
}

export function GitHubConnectModal({
  isOpen,
  onClose,
  onSuccess,
  oauthConfigured = true,
}: GitHubConnectModalProps) {
  const [activeTab, setActiveTab] = useState<'oauth' | 'token'>(
    oauthConfigured ? 'oauth' : 'token'
  );
  const [tokenInput, setTokenInput] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  if (!isOpen) return null;

  const copyToClipboard = (text: string, fieldId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleTokenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = tokenInput.trim();
    if (!token) {
      setError('Please enter a GitHub Personal Access Token.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await connectGitHubToken(token);
      setTokenInput('');
      onSuccess?.();
      onClose();
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail
          : 'Failed to connect with GitHub token. Please verify the token permissions.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-lg rounded-2xl p-6 shadow-2xl relative"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-strong)',
        }}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
          aria-label="Close modal"
        >
          <X size={16} />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-5">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'var(--primary-subtle)', color: 'var(--primary-hover)' }}
          >
            <Shield size={20} />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Connect GitHub</h3>
            <p className="text-xs text-zinc-400">
              Authorize access to inspect repositories and perform code reviews
            </p>
          </div>
        </div>

        {/* Connection Mode Tabs */}
        <div className="flex border-b border-white/10 mb-4">
          <button
            type="button"
            onClick={() => {
              setActiveTab('oauth');
              setError(null);
            }}
            className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === 'oauth'
                ? 'border-indigo-500 text-white font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Globe size={13} />
            <span>GitHub OAuth</span>
            {oauthConfigured && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300">
                Ready
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('token');
              setError(null);
            }}
            className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === 'token'
                ? 'border-indigo-500 text-white font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Key size={13} />
            <span>Personal Access Token</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">
              Instant
            </span>
          </button>
        </div>

        {/* Tab 1: GitHub OAuth */}
        {activeTab === 'oauth' && (
          <div className="space-y-4">
            {!oauthConfigured && (
              <div
                className="rounded-xl p-3.5 text-xs space-y-2.5 border"
                style={{
                  background: 'rgba(245, 158, 11, 0.08)',
                  borderColor: 'rgba(245, 158, 11, 0.25)',
                  color: 'var(--text-primary)',
                }}
              >
                <div className="flex items-center gap-2 font-medium text-amber-400">
                  <AlertCircle size={15} className="flex-shrink-0" />
                  <span>OAuth Not Yet Configured in backend/.env</span>
                </div>
                <p className="text-zinc-300 leading-relaxed text-[11.5px]">
                  To enable 1-click OAuth, create an OAuth app on GitHub and set{' '}
                  <code className="px-1 py-0.5 rounded bg-black/40 text-amber-300 font-mono text-[11px]">
                    GITHUB_CLIENT_ID
                  </code>{' '}
                  and{' '}
                  <code className="px-1 py-0.5 rounded bg-black/40 text-amber-300 font-mono text-[11px]">
                    GITHUB_CLIENT_SECRET
                  </code>{' '}
                  in <code className="px-1 py-0.5 rounded bg-black/40 text-zinc-200 font-mono text-[11px]">backend/.env</code>.
                </p>

                <div className="rounded-lg p-2.5 bg-black/40 border border-white/5 space-y-1.5 font-mono text-[11px]">
                  <div className="flex items-center justify-between text-zinc-300">
                    <span className="text-zinc-400">Homepage URL:</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard('http://localhost:3000', 'homepage')}
                      className="flex items-center gap-1 text-zinc-300 hover:text-white"
                    >
                      <span>http://localhost:3000</span>
                      {copiedField === 'homepage' ? <CheckCheck size={11} className="text-emerald-400" /> : <Copy size={11} />}
                    </button>
                  </div>
                  <div className="flex items-center justify-between text-zinc-300">
                    <span className="text-zinc-400">Callback URL:</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard('http://localhost:8000/api/github/callback', 'callback')}
                      className="flex items-center gap-1 text-zinc-300 hover:text-white"
                    >
                      <span>http://localhost:8000/api/github/callback</span>
                      {copiedField === 'callback' ? <CheckCheck size={11} className="text-emerald-400" /> : <Copy size={11} />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <a
                    href="https://github.com/settings/developers"
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-amber-300 hover:underline inline-flex items-center gap-1"
                  >
                    <span>Open GitHub Developer Settings</span>
                    <ExternalLink size={10} />
                  </a>
                  <button
                    type="button"
                    onClick={() => setActiveTab('token')}
                    className="text-[11px] text-indigo-400 hover:underline"
                  >
                    Or use Token instead →
                  </button>
                </div>
              </div>
            )}

            <div
              className="rounded-lg p-3 text-xs flex flex-col gap-2"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
            >
              <div className="font-medium text-zinc-200 mb-0.5">Permissions Granted:</div>
              <div className="flex items-center gap-2 text-emerald-400">
                <Check size={14} className="flex-shrink-0" />
                <span>Repository read access (tree, branches, commits, content)</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <Check size={14} className="flex-shrink-0" />
                <span>Basic profile information (username, avatar)</span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400 mt-1 pt-2 border-t border-white/5">
                <Shield size={13} className="flex-shrink-0 text-zinc-400" />
                <span>No write or commit permissions requested</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-2 text-xs font-medium rounded-lg text-zinc-300 hover:text-white hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => connectGitHub()}
                className="px-4 py-2 text-xs font-medium rounded-lg text-white flex items-center gap-1.5 transition-all shadow-md"
                style={{ background: 'var(--primary)' }}
              >
                <span>Continue with GitHub</span>
                <ExternalLink size={13} />
              </button>
            </div>
          </div>
        )}

        {/* Tab 2: Personal Access Token */}
        {activeTab === 'token' && (
          <form onSubmit={handleTokenSubmit} className="space-y-4">
            <p className="text-xs text-zinc-300 leading-relaxed">
              Connect instantly without setting up an OAuth application. Your token is encrypted at rest
              using AES-GCM and stored securely on your server.
            </p>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-start gap-2">
                <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label
                htmlFor="github-token-input"
                className="block text-xs font-medium text-zinc-300 mb-1.5"
              >
                GitHub Personal Access Token
              </label>
              <div className="relative">
                <input
                  id="github-token-input"
                  type={showToken ? 'text' : 'password'}
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  disabled={loading}
                  className="w-full pl-3 pr-10 py-2 rounded-lg text-xs font-mono outline-none transition-all disabled:opacity-50"
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    color: 'var(--text-primary)',
                  }}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white transition-colors"
                  aria-label={showToken ? 'Hide token' : 'Show token'}
                >
                  {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[11px] text-zinc-400">
                  Required scopes: <code className="text-zinc-300 font-mono">repo</code>,{' '}
                  <code className="text-zinc-300 font-mono">read:user</code>
                </span>
                <a
                  href="https://github.com/settings/tokens/new?scopes=repo,read:user&description=AI+Code+Reviewer"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-indigo-400 hover:underline inline-flex items-center gap-1"
                >
                  <span>Generate token</span>
                  <ExternalLink size={10} />
                </a>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-3.5 py-2 text-xs font-medium rounded-lg text-zinc-300 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !tokenInput.trim()}
                className="px-4 py-2 text-xs font-medium rounded-lg text-white flex items-center gap-1.5 transition-all shadow-md disabled:opacity-50"
                style={{ background: 'var(--primary)' }}
              >
                {loading ? (
                  <>
                    <Loader2 size={13} className="animate-spin" />
                    <span>Verifying & Connecting...</span>
                  </>
                ) : (
                  <>
                    <Key size={13} />
                    <span>Connect Token</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default GitHubConnectModal;
