const CELL = 7;
const GAP = 2;

function level(count, max) {
  if (count <= 0) return 0;
  const r = count / max;
  if (r > 0.6) return 4;
  if (r > 0.35) return 3;
  if (r > 0.15) return 2;
  return 1;
}

export default function Heatmap({ days, weeks = 53 }) {
  // Align so the last column ends on the last day; the first column starts on a Sunday.
  const slice = days.slice(-(weeks * 7 - (6 - new Date(days.at(-1).date).getUTCDay())));
  const firstDow = new Date(slice[0].date).getUTCDay();
  // Use the 95th percentile as "max" so a single outlier day doesn't wash out the rest.
  const sorted = slice.map((d) => d.count).filter(Boolean).sort((a, b) => a - b);
  const max = sorted[Math.floor(sorted.length * 0.95)] || 1;

  const pitch = CELL + GAP;
  const cols = Math.ceil((slice.length + firstDow) / 7);

  return (
    <svg
      className="heatmap"
      viewBox={`0 0 ${cols * pitch - GAP} ${7 * pitch - GAP}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Contribution heatmap"
    >
      {slice.map((d, i) => {
        const idx = i + firstDow;
        return (
          <rect
            key={d.date}
            x={Math.floor(idx / 7) * pitch}
            y={(idx % 7) * pitch}
            width={CELL}
            height={CELL}
            rx={1.6}
            className={`hm-l${level(d.count, max)}`}
          />
        );
      })}
    </svg>
  );
}
