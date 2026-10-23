import React, { useState, useEffect } from 'react';
import { Key, Shield, Check, X, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { getOperatorKey, setOperatorKey } from '../../utils/auth';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSaved }) => {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [testStatus, setTestStatus] = useState<'IDLE' | 'TESTING' | 'VALID' | 'INVALID'>('IDLE');
  const [testMessage, setTestMessage] = useState('');

  useEffect(() => {
    if (isOpen) {
      setApiKey(getOperatorKey() || '');
      setSavedSuccess(false);
      setTestStatus('IDLE');
      setTestMessage('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    setOperatorKey(apiKey.trim());
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      if (onSaved) onSaved();
      onClose();
    }, 800);
  };

  const handleClear = () => {
    setApiKey('');
    setOperatorKey('');
    setTestStatus('IDLE');
    setTestMessage('');
  };

  const testKey = async () => {
    if (!apiKey.trim()) {
      setTestStatus('INVALID');
      setTestMessage('Please enter a key to test.');
      return;
    }
    setTestStatus('TESTING');
    try {
      const res = await fetch('/api/devices/scan', {
        method: 'POST',
        headers: { 'X-NetWatch-Key': apiKey.trim() }
      });
      if (res.status === 200 || res.status === 429) {
        setTestStatus('VALID');
        setTestMessage(res.status === 429 ? 'Key validated! (Cooldown active)' : 'Key validated successfully!');
      } else if (res.status === 401) {
        setTestStatus('INVALID');
        setTestMessage('Authentication failed: Invalid operator key.');
      } else {
        setTestStatus('VALID');
        setTestMessage(`Server responded with HTTP ${res.status}.`);
      }
    } catch {
      setTestStatus('INVALID');
      setTestMessage('Could not connect to backend server.');
    }
  };

  return (
    <div className="noc-modal-backdrop" onClick={onClose}>
      <div className="noc-modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '480px' }}>
        <div className="noc-modal-header">
          <div className="noc-modal-title-group">
            <Key size={18} style={{ color: 'var(--accent-cyan)' }} />
            <h3 className="noc-modal-title">Operator Authentication Key</h3>
          </div>
          <button className="noc-modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="noc-modal-body">
          <p className="noc-modal-message">
            Supply the <strong style={{ color: 'var(--accent-cyan)' }}>NETWATCH_API_KEY</strong> configured on your server.
            Privileged operations like manual LAN rescans and alert acknowledgments require this key.
            Credentials are kept in <strong style={{ color: 'var(--text-main)' }}>sessionStorage</strong> only and never leaked into static bundles.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>
              OPERATOR API KEY
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="Enter server API key..."
                className="devices-search-input mono"
                style={{ width: '100%', paddingRight: '40px', fontSize: '13px' }}
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                style={{
                  position: 'absolute',
                  right: '8px',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer'
                }}
                title={showKey ? 'Hide key' : 'Show key'}
              >
                {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {testStatus !== 'IDLE' && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              padding: '8px 12px',
              borderRadius: '4px',
              background: testStatus === 'VALID' ? 'rgba(16, 185, 129, 0.12)' : testStatus === 'TESTING' ? 'rgba(0, 212, 255, 0.1)' : 'rgba(239, 68, 68, 0.12)',
              color: testStatus === 'VALID' ? '#10b981' : testStatus === 'TESTING' ? 'var(--accent-cyan)' : '#ef4444',
              border: `1px solid ${testStatus === 'VALID' ? 'rgba(16, 185, 129, 0.3)' : testStatus === 'TESTING' ? 'rgba(0, 212, 255, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
            }}>
              {testStatus === 'VALID' ? <Check size={14} /> : testStatus === 'TESTING' ? <Shield size={14} /> : <AlertCircle size={14} />}
              <span>{testMessage}</span>
            </div>
          )}
        </div>

        <div className="noc-modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={testKey}
              className="noc-btn-secondary"
              disabled={testStatus === 'TESTING' || !apiKey.trim()}
            >
              Test Key
            </button>
            {apiKey && (
              <button
                type="button"
                onClick={handleClear}
                className="noc-btn-secondary"
                style={{ color: 'var(--status-critical)' }}
              >
                Clear
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="noc-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="noc-btn-ack"
              style={{ background: '#10b981', color: '#fff', borderColor: '#059669' }}
              onClick={handleSave}
            >
              {savedSuccess ? <Check size={14} /> : <Shield size={14} />}
              <span>{savedSuccess ? 'Saved' : 'Save Session Key'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
