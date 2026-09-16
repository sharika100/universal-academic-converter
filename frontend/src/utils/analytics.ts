// Decoupled Telemetry Utility for Universal Academic Format Converter

export function getOrCreateSessionId(): { sessionId: string; isReturning: boolean } {
  const SESSION_KEY = 'univ_academic_analytics_session_id';
  const VISITED_KEY = 'univ_academic_analytics_visited';

  let sessionId = sessionStorage.getItem(SESSION_KEY);
  const isReturning = localStorage.getItem(VISITED_KEY) === 'true';

  if (!sessionId) {
    sessionId = 'sess_' + (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36));
    sessionStorage.setItem(SESSION_KEY, sessionId);
  }

  localStorage.setItem(VISITED_KEY, 'true');

  return { sessionId, isReturning };
}

export function detectBrowserFamily(): string {
  const userAgent = navigator.userAgent;
  if (userAgent.includes('Firefox/')) return 'Firefox';
  if (userAgent.includes('Edg/')) return 'Edge';
  if (userAgent.includes('Chrome/')) return 'Chrome';
  if (userAgent.includes('Safari/')) return 'Safari';
  if (userAgent.includes('OPR/') || userAgent.includes('Opera/')) return 'Opera';
  return 'Other';
}

export interface EventPayload {
  event_type: 'page_view' | 'conversion_attempt' | 'conversion_result' | 'download_click';
  conversion_type?: string;
  destination_template?: string;
  status?: 'started' | 'completed' | 'failed';
  upload_time_ms?: number;
  conversion_time_ms?: number;
  download_time_ms?: number;
  total_time_ms?: number;
  validation_passed?: boolean;
  compilation_passed?: boolean;
}

export async function logAnalyticsEvent(payload: EventPayload): Promise<void> {
  try {
    const { sessionId, isReturning } = getOrCreateSessionId();
    const browserFamily = detectBrowserFamily();

    const requestBody = {
      session_id: sessionId,
      is_returning: isReturning,
      browser_family: browserFamily,
      ...payload,
    };

    fetch('/api/analytics/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
      keepalive: true,
    }).catch(() => {
      // Fire-and-forget: silently swallow network/analytics errors
    });
  } catch (e) {
    // Fail-safe wrapper
  }
}

export async function logAnalyticsError(errorCategory: string, errorCode?: string, conversionType?: string, destinationTemplate?: string): Promise<void> {
  try {
    const { sessionId } = getOrCreateSessionId();
    fetch('/api/analytics/error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        error_category: errorCategory,
        error_code: errorCode,
        conversion_type: conversionType,
        destination_template: destinationTemplate,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch (e) {}
}

export async function logAnalyticsFeedback(rating: number, isUseful: boolean, feedbackText?: string, conversionType?: string): Promise<void> {
  try {
    const { sessionId } = getOrCreateSessionId();
    fetch('/api/analytics/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        rating,
        is_useful: isUseful,
        feedback_text: feedbackText,
        conversion_type: conversionType,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch (e) {}
}
