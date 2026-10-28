/** Linked review nodes converge on a checked review: graph reasoning + evidence. */
export default function BrandMark({ className = '' }: { className?: string }) {
  return <svg viewBox="0 0 64 64" className={className} role="img" aria-label="NeuroGraph connected review mark">
    <rect width="64" height="64" rx="16" fill="#12685f"/>
    <g fill="none" stroke="#d9eee7" strokeWidth="2.5" strokeLinecap="round"><path d="M17 18 33 30 45 15M17 18l1 27 15-15 12 17M33 30l-1-16M18 45l26 2"/></g>
    <g fill="#fffefa"><circle cx="17" cy="18" r="4.5"/><circle cx="45" cy="15" r="4.5"/><circle cx="32" cy="14" r="3"/><circle cx="18" cy="45" r="4.5"/><circle cx="33" cy="30" r="5.5"/></g>
    <circle cx="45" cy="46" r="10" fill="#e8c485" stroke="#12685f" strokeWidth="2"/>
    <path d="m40 46 3.5 3.5 6-7" fill="none" stroke="#174f47" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>;
}
