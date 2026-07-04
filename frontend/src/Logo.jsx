// Logo.jsx — Dispensa brand mark, recreated as scalable SVG (no image asset).
//
// Exports:
//   <LogoIcon />    — the capsule + cross + pixel-dissolve icon only
//   <LogoLockup />  — icon + "Dispensa" wordmark + optional subtitle
//
// Brand palette: green #22A45D, navy #0E2A47. Uses gradients + a gloss
// highlight so it reads as premium at any size.

export function LogoIcon({ className = 'w-9 h-9', title = 'Dispensa' }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      fill="none"
      role="img"
      aria-label={title}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="dz-green" x1="22" y1="6" x2="40" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3CC776" />
          <stop offset="1" stopColor="#1E9E55" />
        </linearGradient>
        <linearGradient id="dz-navy" x1="24" y1="32" x2="40" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1C4C70" />
          <stop offset="1" stopColor="#0C2743" />
        </linearGradient>
        <clipPath id="dz-cap">
          <rect x="22" y="6" width="20" height="52" rx="10" />
        </clipPath>
      </defs>

      {/* pixel-dissolve — the "digital / AI" motion off the capsule edge */}
      <g fill="#2CB067">
        <rect x="3" y="21" width="3" height="3" rx="0.7" opacity="0.35" />
        <rect x="8" y="16" width="3.6" height="3.6" rx="0.8" opacity="0.55" />
        <rect x="8" y="27" width="3.6" height="3.6" rx="0.8" opacity="0.55" />
        <rect x="13" y="11" width="4.4" height="4.4" rx="1" opacity="0.8" />
        <rect x="13" y="31" width="4.4" height="4.4" rx="1" opacity="0.8" />
      </g>

      {/* capsule body */}
      <g clipPath="url(#dz-cap)">
        <rect x="22" y="6" width="20" height="26" fill="url(#dz-green)" />
        <rect x="22" y="32" width="20" height="26" fill="url(#dz-navy)" />

        {/* gloss highlight on the green half */}
        <ellipse cx="31" cy="14" rx="7.5" ry="4.2" fill="#ffffff" opacity="0.16" />
        <path d="M25.5 12.2 Q31.5 8.6 38 12" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" opacity="0.55" fill="none" />

        {/* light seam between the halves */}
        <rect x="22" y="30.6" width="20" height="1.7" fill="#F3F6FA" opacity="0.92" />
      </g>

      {/* medical cross on the navy half */}
      <g fill="#ffffff">
        <rect x="30" y="39" width="4" height="12" rx="1.3" />
        <rect x="26" y="43" width="12" height="4" rx="1.3" />
      </g>
    </svg>
  )
}

export function LogoLockup({ iconClass = 'w-11 h-11', subtitle = true, tone = 'light', className = '' }) {
  const wordmark = tone === 'dark' ? 'text-[#0E2A47]' : 'text-white'
  const subEnd = tone === 'dark' ? 'text-slate-500' : 'text-slate-400'
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <LogoIcon className={iconClass} />
      <div className="leading-none">
        <h1 className={`text-[26px] font-black tracking-tight ${wordmark}`}>Dispensa</h1>
        {subtitle && (
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] mt-1.5">
            <span className="text-[#0D9488]">AI-Powered</span>
            <span className={subEnd}> Pharmacy Management</span>
          </p>
        )}
      </div>
    </div>
  )
}
