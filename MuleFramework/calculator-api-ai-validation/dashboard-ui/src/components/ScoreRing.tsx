interface Props {
  value: number;
  label: string;
  sublabel?: string;
  color?: string;
  size?: number;
  animated?: boolean;
}

export function scoreColor(v: number): string {
  if (v >= 90) return '#22c55e';
  if (v >= 75) return '#f59e0b';
  return '#ef4444';
}

export function ScoreRing({ value, label, sublabel, color, size = 100, animated = true }: Props) {
  const c = color ?? scoreColor(value);
  const strokeWidth = size < 80 ? 7 : 9;
  const r = (size - strokeWidth * 2) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(Math.max(value, 0), 100);
  const offset = circ - (pct / 100) * circ;
  const glowId = `glow-${label.replace(/\s+/g, '')}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.6rem', minWidth: size }}>
      {/* Ring */}
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', overflow: 'visible' }}>
          <defs>
            <filter id={glowId}>
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {/* Track */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke="var(--ring-track)" strokeWidth={strokeWidth}
          />
          {/* Value arc */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={c} strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            filter={`url(#${glowId})`}
            style={{
              transition: animated ? 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)' : undefined,
            }}
          />
        </svg>
        {/* Center value */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: '0',
        }}>
          <span style={{
            fontSize: size < 80 ? '1rem' : '1.35rem',
            fontWeight: 800,
            color: c,
            lineHeight: 1,
            letterSpacing: '-0.02em',
            fontFamily: 'Inter, system-ui, sans-serif',
          }}>
            {value}
          </span>
          {sublabel && (
            <span style={{ fontSize: '0.55rem', color: 'var(--text-dim)', marginTop: '0.1rem', fontWeight: 500 }}>
              {sublabel}
            </span>
          )}
        </div>
      </div>
      {/* Label */}
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)',
          letterSpacing: '0.05em', textTransform: 'uppercase',
        }}>
          {label}
        </div>
      </div>
    </div>
  );
}
