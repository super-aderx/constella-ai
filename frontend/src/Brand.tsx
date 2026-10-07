/** The Constella mark (five stars, peach hub), the name, and the AI badge. Follows the theme. */
export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 text-[19px] font-bold tracking-[-0.03em] text-action">
      <svg viewBox="0 0 48 48" width={26} height={26} aria-hidden fill="var(--action)">
        <path d="M10 34 L18 13 L30 23 L38 8 M30 23 L36 39 L10 34" fill="none" stroke="var(--action)" strokeWidth={2.75} strokeLinecap="round" />
        <circle cx={10} cy={34} r={3} />
        <circle cx={18} cy={13} r={3} />
        <circle cx={38} cy={8} r={2.5} />
        <circle cx={36} cy={39} r={3.5} />
        <circle cx={30} cy={23} r={5.5} fill="var(--star)" />
      </svg>
      Constella
      <span className="rounded-md bg-action px-1.5 py-0.5 text-[13px] tracking-normal text-on-action">AI</span>
    </span>
  )
}

/** The small constellation glyph that marks generated content. */
export function GenMark({ size = 16 }: { size?: number }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} aria-hidden className="shrink-0 text-action">
      <path d="M3 12 L7 4 L13 8" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={3} cy={12} r={1.8} fill="currentColor" />
      <circle cx={13} cy={8} r={1.8} fill="currentColor" />
      <circle cx={7} cy={4} r={2.6} fill="var(--star)" />
    </svg>
  )
}
