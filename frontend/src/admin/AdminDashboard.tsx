import React, { useState, useEffect } from 'react';
import {
  Activity,
  RefreshCw,
  LogOut,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  Clock,
  Star,
  FileText,
  ShieldCheck,
  UserCheck,
  Layers,
  ArrowLeft,
  MessageSquare,
  Lightbulb,
  Calendar
} from 'lucide-react';

interface AdminDashboardProps {
  token: string;
  username: string;
  onLogout: () => void;
  onBackToConverter: () => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  token,
  username,
  onLogout,
  onBackToConverter,
}) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  const [selectedDays, setSelectedDays] = useState<number | null>(null);

  const fetchMetrics = async (daysOverride?: number | null) => {
    setLoading(true);
    setError(null);
    const activeDays = daysOverride !== undefined ? daysOverride : selectedDays;
    try {
      const queryStr = activeDays ? `?days=${activeDays}` : '';
      const res = await fetch(`/api/admin/analytics${queryStr}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          onLogout();
          return;
        }
        throw new Error(`Failed to load analytics data (HTTP ${res.status})`);
      }

      const analyticsData = await res.json();
      setData(analyticsData);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err: any) {
      setError(err.message || 'Error connecting to analytics backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics(selectedDays);
    const interval = setInterval(() => fetchMetrics(selectedDays), 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, [token, selectedDays]);

  const handleSelectDays = (d: number | null) => {
    setSelectedDays(d);
    fetchMetrics(d);
  };

  if (loading && !data) {
    return (
      <div className="admin-login-page">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#A5B4FC' }}>
          <RefreshCw style={{ width: 24, height: 24 }} />
          <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Loading telemetry metrics...</span>
        </div>
      </div>
    );
  }

  const summary = data?.summary || data?.totals || {};
  const performance = data?.performance || data?.latencies || {};
  const quality = data?.quality_indicators || data?.quality || {};
  const feedbackSummary = data?.user_feedback || data?.feedback_summary || {};
  const workflows = data?.workflows || [];
  const templates = data?.templates || [];
  const errors = data?.error_categories || data?.errors || [];
  const recentFeedback = feedbackSummary?.recent_comments || data?.recent_feedback || [];
  const insights = data?.insights || [];

  return (
    <div className="admin-dashboard-page">
      <div className="admin-dashboard-container">
        {/* Top Header Bar */}
        <div className="admin-header-bar">
          <div className="admin-header-title-group">
            <button
              onClick={onBackToConverter}
              className="admin-btn-icon"
              title="Return to Public Converter"
            >
              <ArrowLeft style={{ width: 18, height: 18 }} />
            </button>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span className="admin-badge admin-badge-primary">
                  Private Admin Dashboard
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Refreshed at {lastRefreshed}
                </span>
              </div>
              <h1>Converter Operational Analytics</h1>
            </div>
          </div>

          <div className="admin-nav-actions">
            <button
              onClick={() => fetchMetrics(selectedDays)}
              disabled={loading}
              className="admin-btn-secondary"
            >
              <RefreshCw style={{ width: 14, height: 14 }} />
              <span>Refresh</span>
            </button>

            <div className="admin-user-pill">
              <span className="admin-user-status-dot"></span>
              <span>{username}</span>
            </div>

            <button
              onClick={onLogout}
              className="admin-btn-danger"
            >
              <LogOut style={{ width: 14, height: 14 }} />
              <span>Logout</span>
            </button>
          </div>
        </div>

        {/* Date Filter Toolbar */}
        <div className="admin-filter-bar">
          <div className="admin-filter-group" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <Calendar style={{ width: 16, height: 16, color: '#6366F1' }} />
            <span style={{ fontWeight: 500 }}>Filter Time Window:</span>
          </div>
          <div className="admin-filter-group">
            {[
              { label: 'Today', days: 1 },
              { label: '7 Days', days: 7 },
              { label: '30 Days', days: 30 },
              { label: 'All Time', days: null }
            ].map((item) => (
              <button
                key={item.label}
                onClick={() => handleSelectDays(item.days)}
                className={`admin-filter-btn ${selectedDays === item.days ? 'active' : ''}`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="admin-error-box" style={{ marginBottom: 24, justifyContent: 'space-between' }}>
            <span>{error}</span>
            <button onClick={() => fetchMetrics(selectedDays)} style={{ background: 'none', border: 'none', color: '#FCA5A5', textDecoration: 'underline', cursor: 'pointer', fontWeight: 600 }}>
              Retry
            </button>
          </div>
        )}

        {/* Measured Insights Section */}
        {insights.length > 0 && (
          <div className="admin-insights-section">
            <h3 className="admin-section-title" style={{ color: '#A5B4FC' }}>
              <Lightbulb style={{ width: 18, height: 18, color: '#F59E0B' }} />
              <span>Factual Measured Insights</span>
            </h3>
            <div className="admin-insights-grid">
              {insights.map((fact: string, idx: number) => (
                <div key={idx} className="admin-insight-item">
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#6366F1', marginTop: 6, flexShrink: 0 }}></span>
                  <span>{fact}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KPI Cards Grid */}
        <div className="admin-kpi-grid">
          {/* Card 1 */}
          <div className="admin-card">
            <div className="admin-card-header">
              <span className="admin-card-title">Total Attempts</span>
              <div className="admin-card-icon">
                <FileText style={{ width: 18, height: 18 }} />
              </div>
            </div>
            <div className="admin-stat-row">
              <span className="admin-stat-value">{summary.total_conversion_attempts ?? summary.total_conversions ?? 0}</span>
              <span style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 600 }}>{summary.successful_conversions ?? summary.completed_conversions ?? 0} completed</span>
            </div>
            <div className="admin-stat-sub">
              Unique Sessions: {summary.total_sessions ?? summary.unique_sessions ?? 0}
            </div>
          </div>

          {/* Card 2 */}
          <div className="admin-card">
            <div className="admin-card-header">
              <span className="admin-card-title">Conversion Success Rate</span>
              <div className="admin-card-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#6EE7B7' }}>
                <TrendingUp style={{ width: 18, height: 18 }} />
              </div>
            </div>
            <div className="admin-stat-row">
              <span className="admin-stat-value">{summary.success_rate_percent ?? summary.success_rate ?? 100}%</span>
              <span style={{ fontSize: '0.75rem', color: '#FCA5A5', fontWeight: 600 }}>{summary.failed_conversions ?? 0} failed</span>
            </div>
            <div className="admin-stat-sub">
              Returning Sessions: {summary.returning_sessions ?? 0}
            </div>
          </div>

          {/* Card 3 */}
          <div className="admin-card">
            <div className="admin-card-header">
              <span className="admin-card-title">P95 Processing Latency</span>
              <div className="admin-card-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8' }}>
                <Clock style={{ width: 18, height: 18 }} />
              </div>
            </div>
            <div className="admin-stat-row">
              <span className="admin-stat-value">
                {performance.p95_processing_time_s ?? (performance.total_time?.p95 ? (performance.total_time.p95 / 1000).toFixed(1) : '0.0')}s
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Avg: {performance.avg_processing_time_s ?? (performance.total_time?.avg ? (performance.total_time.avg / 1000).toFixed(1) : '0.0')}s
              </span>
            </div>
            <div className="admin-stat-sub">
              Avg Upload Latency: {performance.avg_upload_time_s ?? 0.0}s
            </div>
          </div>

          {/* Card 4 */}
          <div className="admin-card">
            <div className="admin-card-header">
              <span className="admin-card-title">User Satisfaction</span>
              <div className="admin-card-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#FCD34D' }}>
                <Star style={{ width: 18, height: 18 }} />
              </div>
            </div>
            <div className="admin-stat-row">
              <span className="admin-stat-value">
                {feedbackSummary.average_rating ?? feedbackSummary.avg_rating ?? '5.0'} / 5
              </span>
              <span style={{ fontSize: '0.75rem', color: '#FCD34D', fontWeight: 600 }}>
                {feedbackSummary.useful_percentage ?? 100}% Useful
              </span>
            </div>
            <div className="admin-stat-sub">
              Total Feedback Responses: {feedbackSummary.total_responses ?? feedbackSummary.total_ratings ?? 0}
            </div>
          </div>
        </div>

        {/* Operational Quality Metrics Bar */}
        <div className="admin-card" style={{ marginBottom: 28 }}>
          <h3 className="admin-section-title">
            <ShieldCheck style={{ width: 18, height: 18, color: '#10B981' }} />
            <span>Conversion Quality & Integrity Pipeline Verification</span>
          </h3>

          <div className="admin-grid-2" style={{ marginBottom: 0 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 6 }}>
                <span style={{ color: 'var(--text-muted)' }}>Structural Validation Pass Rate</span>
                <span style={{ fontWeight: 600, color: '#10B981' }}>{quality.validation_pass_rate || 0}%</span>
              </div>
              <div className="admin-progress-bg">
                <div
                  className="admin-progress-fill"
                  style={{ width: `${quality.validation_pass_rate || 0}%`, background: '#10B981' }}
                ></div>
              </div>
              <p style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: 6 }}>
                Verifies author count, section structure, and table/figure completeness.
              </p>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 6 }}>
                <span style={{ color: 'var(--text-muted)' }}>LaTeX Sandbox Compilation Pass Rate</span>
                <span style={{ fontWeight: 600, color: '#6366F1' }}>{quality.compilation_pass_rate || 0}%</span>
              </div>
              <div className="admin-progress-bg">
                <div
                  className="admin-progress-fill"
                  style={{ width: `${quality.compilation_pass_rate || 0}%`, background: '#6366F1' }}
                ></div>
              </div>
              <p style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: 6 }}>
                Verifies zero pdflatex syntax errors and successful PDF preview build.
              </p>
            </div>
          </div>
        </div>

        {/* Grid: Workflow Usage & Destination Templates */}
        <div className="admin-grid-2">
          {/* Top Workflows */}
          <div className="admin-card">
            <h3 className="admin-section-title">
              <Layers style={{ width: 18, height: 18, color: '#38BDF8' }} />
              <span>Format Workflow Distribution</span>
            </h3>

            {workflows.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No workflow telemetry recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {workflows.map((wf: any, idx: number) => {
                  const maxCount = workflows[0]?.count || 1;
                  const pct = Math.round((wf.count / maxCount) * 100);
                  return (
                    <div key={idx}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-main)' }}>{wf.conversion_type}</span>
                        <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{wf.count} ({wf.percentage}%)</span>
                      </div>
                      <div className="admin-progress-bg">
                        <div className="admin-progress-fill" style={{ width: `${pct}%`, background: '#38BDF8' }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Top Destination Templates */}
          <div className="admin-card">
            <h3 className="admin-section-title">
              <FileText style={{ width: 18, height: 18, color: '#C084FC' }} />
              <span>Destination Publisher Templates</span>
            </h3>

            {templates.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No template telemetry recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {templates.map((tpl: any, idx: number) => {
                  const maxCount = templates[0]?.count || 1;
                  const pct = Math.round((tpl.count / maxCount) * 100);
                  return (
                    <div key={idx}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                        <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>{tpl.template_name}</span>
                        <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{tpl.count} ({tpl.percentage}%)</span>
                      </div>
                      <div className="admin-progress-bg">
                        <div className="admin-progress-fill" style={{ width: `${pct}%`, background: '#C084FC' }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Error Breakdown Section */}
        <div className="admin-card" style={{ marginBottom: 28 }}>
          <h3 className="admin-section-title">
            <AlertTriangle style={{ width: 18, height: 18, color: '#F59E0B' }} />
            <span>Categorized Operational Error Log</span>
          </h3>

          {errors.length === 0 ? (
            <div className="admin-insight-item" style={{ borderColor: 'rgba(16, 185, 129, 0.3)', color: '#6EE7B7' }}>
              <CheckCircle style={{ width: 18, height: 18, flexShrink: 0 }} />
              <span>Zero errors recorded in active telemetry window. Perfect conversion status!</span>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Error Category</th>
                    <th>Error Code</th>
                    <th style={{ textAlign: 'right' }}>Occurrences</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.map((err: any, idx: number) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 500 }}>{err.category}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#FCD34D' }}>{err.error_code || 'N/A'}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600, color: '#FCA5A5' }}>{err.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Voluntary User Feedback Table */}
        <div className="admin-card">
          <h3 className="admin-section-title">
            <MessageSquare style={{ width: 18, height: 18, color: '#6366F1' }} />
            <span>Recent Voluntary User Feedback</span>
          </h3>

          {recentFeedback.length === 0 ? (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No user feedback comments submitted yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {recentFeedback.map((fb: any, idx: number) => (
                <div key={idx} className="admin-feedback-card">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ display: 'flex', color: '#F59E0B' }}>
                        {[...Array(fb.rating || 5)].map((_, i) => (
                          <Star key={i} style={{ width: 14, height: 14, fill: '#F59E0B' }} />
                        ))}
                      </div>
                      <span className={`admin-badge ${fb.is_useful ? 'admin-badge-success' : 'admin-badge-error'}`}>
                        {fb.is_useful ? 'Useful' : 'Issues Logged'}
                      </span>
                    </div>
                    <span style={{ fontSize: '0.725rem', color: 'var(--text-dim)' }}>{fb.created_at || 'Just now'}</span>
                  </div>
                  {fb.feedback_text ? (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontStyle: 'italic' }}>"{fb.feedback_text}"</p>
                  ) : (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No text comment provided.</p>
                  )}
                  {fb.conversion_type && (
                    <div style={{ marginTop: 6, fontSize: '0.725rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      Workflow: {fb.conversion_type}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
