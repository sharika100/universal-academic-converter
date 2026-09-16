import React, { useState } from 'react';
import { Star, ThumbsUp, ThumbsDown, Send, CheckCircle2 } from 'lucide-react';
import { logAnalyticsFeedback } from '../utils/analytics';

interface FeedbackCardProps {
  conversionType?: string;
}

export const FeedbackCard: React.FC<FeedbackCardProps> = ({ conversionType }) => {
  const [rating, setRating] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [isUseful, setIsUseful] = useState<boolean>(true);
  const [comment, setComment] = useState<string>('');
  const [submitted, setSubmitted] = useState<boolean>(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    logAnalyticsFeedback(rating, isUseful, comment, conversionType);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="mt-6 bg-slate-900/60 border border-emerald-500/30 rounded-xl p-6 text-center shadow-lg backdrop-blur-md">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 mb-3">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <h4 className="text-lg font-semibold text-slate-100">Thank you for your feedback!</h4>
        <p className="text-sm text-slate-400 mt-1">Your response helps us refine document extraction and LaTeX compilation accuracy.</p>
      </div>
    );
  }

  return (
    <div className="mt-8 bg-slate-900/70 border border-indigo-500/20 rounded-xl p-6 shadow-xl backdrop-blur-md">
      <h4 className="text-lg font-semibold text-slate-100 mb-1">How was your conversion experience?</h4>
      <p className="text-xs text-slate-400 mb-4">Voluntary anonymous feedback to improve parser formatting & sandbox compilation.</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Star Rating */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-2">Overall Quality Rating</label>
          <div className="flex items-center space-x-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                type="button"
                key={star}
                onMouseEnter={() => setHoverRating(star)}
                onMouseLeave={() => setHoverRating(0)}
                onClick={() => setRating(star)}
                className="p-1 text-amber-400 hover:scale-110 transition-transform focus:outline-none"
              >
                <Star
                  className={`w-6 h-6 ${
                    (hoverRating || rating) >= star
                      ? 'fill-amber-400 text-amber-400'
                      : 'text-slate-600'
                  }`}
                />
              </button>
            ))}
            <span className="ml-3 text-xs text-slate-400 font-mono">
              {hoverRating || rating} / 5
            </span>
          </div>
        </div>

        {/* Useful Toggle */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-2">Was the generated package useful?</label>
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => setIsUseful(true)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all border ${
                isUseful
                  ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200'
                  : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              <ThumbsUp className="w-4 h-4" />
              <span>Yes, preserved structure</span>
            </button>
            <button
              type="button"
              onClick={() => setIsUseful(false)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition-all border ${
                !isUseful
                  ? 'bg-rose-600/30 border-rose-500 text-rose-200'
                  : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              <ThumbsDown className="w-4 h-4" />
              <span>No, issues encountered</span>
            </button>
          </div>
        </div>

        {/* Optional Comment */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">Optional Comments / Suggestions</label>
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Share any formatting, figure, or equation issues you observed (do not include sensitive manuscript text)..."
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <button
          type="submit"
          className="flex items-center justify-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all focus:outline-none"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Submit Voluntary Feedback</span>
        </button>
      </form>
    </div>
  );
};
