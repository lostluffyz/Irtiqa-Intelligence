'use client';

/* ── Minimal SVG icon components — no icon package dependency. ── */

interface IconProps {
  className?: string;
}

function SvgBase({
  children,
  className = 'h-5 w-5',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

export function DashboardIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </SvgBase>
  );
}

export function CompaniesIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M3 21h18" />
      <path d="M5 21V5a2 2 0 012-2h10a2 2 0 012 2v16" />
      <path d="M9 7h1" />
      <path d="M9 11h1" />
      <path d="M9 15h1" />
      <path d="M14 7h1" />
      <path d="M14 11h1" />
      <path d="M14 15h1" />
    </SvgBase>
  );
}

export function LeadsIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </SvgBase>
  );
}

export function DiscoveryIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
      <path d="M11 8v6" />
      <path d="M8 11h6" />
    </SvgBase>
  );
}

export function JobsIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </SvgBase>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
    </SvgBase>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </SvgBase>
  );
}

export function SignOutIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </SvgBase>
  );
}

export function ChevronRightIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <polyline points="9 18 15 12 9 6" />
    </SvgBase>
  );
}
