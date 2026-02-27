"use client";

interface InfoHintProps {
  text: string;
}

export function InfoHint({ text }: InfoHintProps) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label="Field description"
        className="ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full border border-white/30 text-[10px] leading-none text-white/70 hover:border-white/60 hover:text-white focus:outline-none focus:ring-1 focus:ring-cyan-400"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-[140] mt-2 w-72 -translate-x-1/2 rounded-md border border-white/20 bg-slate-950/95 px-2.5 py-2 text-[11px] normal-case tracking-normal text-white/90 opacity-0 shadow-xl transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
