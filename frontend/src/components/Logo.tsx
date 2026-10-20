/** Brand mark: three milestones feeding one green light. */
export default function Logo() {
  return (
    <span className="brand">
      <svg className="brand__mark" viewBox="0 0 26 26" aria-hidden="true">
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#5b3fb8" />
            <stop offset="1" stopColor="#b4609f" />
          </linearGradient>
        </defs>
        <path d="M4 5h5M4 13h5M4 21h5" stroke="url(#lg)" strokeWidth="2" strokeLinecap="round" />
        <path d="M9 5c5 0 5 8 9 8M9 21c5 0 5-8 9-8M9 13h9" stroke="url(#lg)" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <circle cx="21" cy="13" r="3.2" fill="url(#lg)" />
      </svg>
      <span className="brand__name">
        TrialFlow<span className="brand__dot">.</span>
      </span>
    </span>
  );
}
