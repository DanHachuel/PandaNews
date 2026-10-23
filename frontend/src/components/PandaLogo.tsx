export function PandaLogo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-label="PandaNews">
      <rect width="100" height="100" rx="20" fill="#0b1220" stroke="#22c55e" strokeWidth="4" />
      <circle cx="25" cy="28" r="13" fill="#e6edf3" />
      <circle cx="75" cy="28" r="13" fill="#e6edf3" />
      <circle cx="50" cy="52" r="30" fill="#e6edf3" />
      <ellipse cx="37" cy="48" rx="9" ry="11" fill="#0b1220" transform="rotate(-15 37 48)" />
      <ellipse cx="63" cy="48" rx="9" ry="11" fill="#0b1220" transform="rotate(15 63 48)" />
      <circle cx="38" cy="49" r="3" fill="#22c55e" />
      <circle cx="62" cy="49" r="3" fill="#22c55e" />
      <ellipse cx="50" cy="62" rx="5" ry="4" fill="#0b1220" />
    </svg>
  );
}
