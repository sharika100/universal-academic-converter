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
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="flex items-center space-x-3 text-indigo-400">
          <RefreshCw className="w-6 h-6 animate-spin" />
          <span className="text-sm font-medium">Loading telemetry metrics...</span>
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
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-4 md:p-8">
      {/* Top Header */}
      <div className="max-w-7xl mx-auto mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-slate-800">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBackToConverter}
            className="p-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
            title="Return to Public Converter"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center space-x-3">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                Private Admin Dashboard
              </span>
              <span className="text-xs text-slate-500">Refreshed at {lastRefreshed}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white mt-1">Converter Operational Analytics</h1>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchMetrics(selectedDays)}
            disabled={loading}
            className="flex items-center space-x-2 px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            <span>Refresh</span>
          </button>

          <div className="flex items-center space-x-2 px-3.5 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-mono text-slate-400">{username}</span>
          </div>

          <button
            onClick={onLogout}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-rose-950/40 border border-rose-900/50 rounded-xl text-xs font-semibold text-rose-300 hover:bg-rose-900/40 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Logout</span>
          </button>
        </div>
      </div>

      {/* Date Filter Toolbar */}
      <div className="max-w-7xl mx-auto mb-6 flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded-xl p-3">
        <div className="flex items-center space-x-2 text-xs text-slate-400">
          <Calendar className="w-4 h-4 text-indigo-400" />
          <span className="font-medium">Filter Time Window:</span>
        </div>
        <div className="flex items-center space-x-2">
          {[
            { label: 'Today', days: 1 },
            { label: '7 Days', days: 7 },
            { label: '30 Days', days: 30 },
            { label: 'All Time', days: null }
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => handleSelectDays(item.days)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedDays === item.days
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'bg-slate-950/80 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="max-w-7xl mx-auto mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => fetchMetrics(selectedDays)} className="underline font-semibold">Retry</button>
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-8">
        {/* Measured Insights Section */}
        {insights.length > 0 && (
          <div className="bg-gradient-to-r from-indigo-950/40 via-slate-900/80 to-slate-900/80 border border-indigo-500/20 rounded-2xl p-6 shadow-xl backdrop-blur-md">
            <h3 className="text-sm font-semibold text-indigo-300 mb-3 flex items-center space-x-2">
              <Lightbulb className="w-4 h-4 text-amber-400" />
              <span>Factual Measured Insights</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {insights.map((fact: string, idx: number) => (
                <div key={idx} className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-200 flex items-start space-x-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0"></span>
                  <span>{fact}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KPI Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Total Attempts</span>
              <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
                <FileText className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-3xl font-bold tracking-tight text-white">{summary.total_conversion_attempts ?? summary.total_conversions ?? 0}</span>
              <span className="text-xs text-emerald-400 font-medium">{summary.successful_conversions ?? summary.completed_conversions ?? 0} completed</span>
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Unique Sessions: {summary.total_sessions ?? summary.unique_sessions ?? 0}
            </div>
          </div>

          {/* Card 2 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Conversion Success Rate</span>
              <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                <TrendingUp className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-3xl font-bold tracking-tight text-white">{summary.success_rate_percent ?? summary.success_rate ?? 100}%</span>
              <span className="text-xs text-rose-400 font-medium">{summary.failed_conversions ?? 0} failed</span>
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Returning Sessions: {summary.returning_sessions ?? 0}
            </div>
          </div>

          {/* Card 3 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">P95 Processing Latency</span>
              <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400">
                <Clock className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-3xl font-bold tracking-tight text-white">
                {performance.p95_processing_time_s ?? (performance.total_time?.p95 ? (performance.total_time.p95 / 1000).toFixed(1) : '0.0')}s
              </span>
              <span className="text-xs text-slate-400 font-mono">
                Avg: {performance.avg_processing_time_s ?? (performance.total_time?.avg ? (performance.total_time.avg / 1000).toFixed(1) : '0.0')}s
              </span>
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Avg Upload Latency: {performance.avg_upload_time_s ?? 0.0}s
            </div>
          </div>

          {/* Card 4 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">User Satisfaction</span>
              <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
                <Star className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-3xl font-bold tracking-tight text-white">
                {feedbackSummary.average_rating ?? feedbackSummary.avg_rating ?? '5.0'} / 5
              </span>
              <span className="text-xs text-amber-400 font-medium">
                {feedbackSummary.useful_percentage ?? 100}% Useful
              </span>
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Total Feedback Responses: {feedbackSummary.total_responses ?? feedbackSummary.total_ratings ?? 0}
            </div>
          </div>
        </div>

        {/* Operational Quality Metrics Bar */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md">
          <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Conversion Quality & Integrity Pipeline Verification</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Structural Validation Pass Rate</span>
                <span className="font-semibold text-emerald-400">{quality.validation_pass_rate || 0}%</span>
              </div>
              <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-emerald-500 h-2.5 rounded-full transition-all duration-500"
                  style={{ width: `${quality.validation_pass_rate || 0}%` }}
                ></div>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Verifies author count, section structure, and table/figure completeness.</p>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">LaTeX Sandbox Compilation Pass Rate</span>
                <span className="font-semibold text-indigo-400">{quality.compilation_pass_rate || 0}%</span>
              </div>
              <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-indigo-500 h-2.5 rounded-full transition-all duration-500"
                  style={{ width: `${quality.compilation_pass_rate || 0}%` }}
                ></div>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Verifies zero pdflatex syntax errors and successful PDF preview build.</p>
            </div>
          </div>
        </div>

        {/* Grid: Workflow Usage & Destination Templates */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Workflows */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-sky-400" />
              <span>Format Workflow Distribution</span>
            </h3>

            {workflows.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No workflow telemetry recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {workflows.map((wf: any, idx: number) => {
                  const maxCount = workflows[0]?.count || 1;
                  const pct = Math.round((wf.count / maxCount) * 100);
                  return (
                    <div key={idx}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300 font-mono text-[11px]">{wf.conversion_type}</span>
                        <span className="text-slate-400 font-medium">{wf.count} ({wf.percentage}%)</span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-sky-500 h-2 rounded-full"
                          style={{ width: `${pct}%` }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Top Destination Templates */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
              <FileText className="w-4 h-4 text-purple-400" />
              <span>Destination Publisher Templates</span>
            </h3>

            {templates.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No template telemetry recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {templates.map((tpl: any, idx: number) => {
                  const maxCount = templates[0]?.count || 1;
                  const pct = Math.round((tpl.count / maxCount) * 100);
                  return (
                    <div key={idx}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300 font-medium">{tpl.template_name}</span>
                        <span className="text-slate-400 font-medium">{tpl.count} ({tpl.percentage}%)</span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-purple-500 h-2 rounded-full"
                          style={{ width: `${pct}%` }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Error Breakdown Section */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md">
          <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Categorized Operational Error Log</span>
          </h3>

          {errors.length === 0 ? (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center space-x-2">
              <CheckCircle className="w-4 h-4" />
              <span>Zero errors recorded in active telemetry telemetry window. Perfect conversion status!</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-medium">
                    <th className="pb-2">Error Category</th>
                    <th className="pb-2">Error Code</th>
                    <th className="pb-2 text-right">Occurrences</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {errors.map((err: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-800/30">
                      <td className="py-2.5 font-medium text-slate-200">{err.category}</td>
                      <td className="py-2.5 font-mono text-amber-300">{err.error_code || 'N/A'}</td>
                      <td className="py-2.5 text-right font-semibold text-rose-400">{err.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Voluntary User Feedback Table */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md">
          <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
            <MessageSquare className="w-4 h-4 text-indigo-400" />
            <span>Recent Voluntary User Feedback</span>
          </h3>

          {recentFeedback.length === 0 ? (
            <p className="text-xs text-slate-500 italic">No user feedback comments submitted yet.</p>
          ) : (
            <div className="space-y-3">
              {recentFeedback.map((fb: any, idx: number) => (
                <div key={idx} className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <div className="flex items-center text-amber-400">
                        {[...Array(fb.rating || 5)].map((_, i) => (
                          <Star key={i} className="w-3.5 h-3.5 fill-amber-400" />
                        ))}
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        fb.is_useful ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {fb.is_useful ? 'Useful' : 'Issues Logged'}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500">{fb.created_at || 'Just now'}</span>
                  </div>
                  {fb.feedback_text ? (
                    <p className="text-xs text-slate-300 italic font-sans">"{fb.feedback_text}"</p>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No text comment provided.</p>
                  )}
                  {fb.conversion_type && (
                    <div className="mt-2 text-[10px] text-slate-500 font-mono">Workflow: {fb.conversion_type}</div>
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
