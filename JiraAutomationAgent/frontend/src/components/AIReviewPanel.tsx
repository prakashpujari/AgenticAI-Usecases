import React from 'react';
import type { ReviewResult } from '../types';

interface Props {
  review: ReviewResult | null;
  isLoading?: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  APPROVED: 'bg-green-50 border-green-300 text-green-800',
  CHANGES_REQUIRED: 'bg-amber-50 border-amber-300 text-amber-800',
};

const STATUS_ICONS: Record<string, string> = {
  APPROVED: '✅',
  CHANGES_REQUIRED: '⚠️',
};

const AIReviewPanel: React.FC<Props> = ({ review, isLoading }) => {
  if (isLoading) {
    return (
      <div className="border rounded-lg p-4 bg-gray-50 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-3" />
        <div className="h-3 bg-gray-200 rounded w-full mb-2" />
        <div className="h-3 bg-gray-200 rounded w-5/6" />
      </div>
    );
  }

  if (!review || !review.status) return null;

  const styleClass =
    STATUS_STYLES[review.status] ?? 'bg-gray-50 border-gray-200 text-gray-800';
  const icon = STATUS_ICONS[review.status] ?? '🔍';

  return (
    <div className={`border rounded-lg p-4 ${styleClass}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <h3 className="font-semibold text-sm">
          AI Review — {review.status.replace('_', ' ')}
        </h3>
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap">{review.feedback}</p>
    </div>
  );
};

export default AIReviewPanel;
