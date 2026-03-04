"use client";

import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type NiceSelectOption<T extends string | number> = {
  value: T;
  label: string;
  hint?: string;
  disabled?: boolean;
};

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export function NiceSelect<T extends string | number>(props: {
  value: T | "";
  onChange: (value: T | "") => void;
  options: Array<NiceSelectOption<T>>;
  placeholder?: string;
  className?: string;
  buttonClassName?: string;
  menuClassName?: string;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  const {
    value,
    onChange,
    options,
    placeholder = "Select…",
    className,
    buttonClassName,
    menuClassName,
    ariaLabel,
    disabled,
  } = props;

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [menuPos, setMenuPos] = useState<{ left: number; top: number; width: number; placement: "bottom" | "top" } | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  const selected = useMemo(() => options.find((o) => o.value === value) ?? null, [options, value]);

  const computeMenuPos = () => {
    const btn = buttonRef.current;
    if (!btn) return;

    const rect = btn.getBoundingClientRect();
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    const width = rect.width;
    const left = clamp(rect.left, 8, Math.max(8, viewportW - width - 8));

    // Keep a conservative menu height to decide placement.
    const estimatedMenuH = Math.min(360, 44 + options.length * 34);
    const spaceBelow = viewportH - rect.bottom;
    const placement: "bottom" | "top" = spaceBelow >= estimatedMenuH + 8 ? "bottom" : "top";
    const top = placement === "bottom" ? rect.bottom + 8 : Math.max(8, rect.top - 8);

    setMenuPos({ left, top, width, placement });
  };

  useEffect(() => {
    if (!open) return;
    computeMenuPos();

    const onResize = () => computeMenuPos();
    const onScroll = () => computeMenuPos();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((prev) => {
          const start = prev >= 0 ? prev : -1;
          for (let i = start + 1; i < options.length; i++) if (!options[i]?.disabled) return i;
          for (let i = 0; i < options.length; i++) if (!options[i]?.disabled) return i;
          return -1;
        });
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((prev) => {
          const start = prev >= 0 ? prev : options.length;
          for (let i = start - 1; i >= 0; i--) if (!options[i]?.disabled) return i;
          for (let i = options.length - 1; i >= 0; i--) if (!options[i]?.disabled) return i;
          return -1;
        });
        return;
      }
      if (e.key === "Enter") {
        if (activeIndex >= 0 && !options[activeIndex]?.disabled) {
          e.preventDefault();
          onChange(options[activeIndex]!.value);
          setOpen(false);
        }
      }
    };
    const onPointerDown = (e: PointerEvent) => {
      const btn = buttonRef.current;
      const target = e.target as Node | null;
      if (btn && target && btn.contains(target)) return;
      // If clicked inside the portal menu, the menu handles it.
      const menuEl = document.getElementById("nice-select-menu");
      if (menuEl && target && menuEl.contains(target)) return;
      setOpen(false);
    };

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true, capture: true } as any);
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);

    return () => {
      window.removeEventListener("resize", onResize as any);
      window.removeEventListener("scroll", onScroll as any, true as any);
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, activeIndex, options, onChange]);

  useEffect(() => {
    if (!open) setActiveIndex(-1);
  }, [open]);

  const buttonText = selected ? selected.label : placeholder;
  const buttonSub = selected?.hint;

  return (
    <div className={className}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        className={
          buttonClassName ??
          "relative w-full rounded-lg bg-black/20 border border-white/15 px-3 py-2 text-sm text-left text-white/90 disabled:opacity-60 hover:border-white/25 focus:outline-none focus:ring-1 focus:ring-cyan-400"
        }
        onClick={() => {
          if (disabled) return;
          setOpen((v) => !v);
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className={`truncate ${selected ? "text-white" : "text-white/60"}`}>{buttonText}</div>
            {buttonSub && <div className="truncate text-[11px] text-white/50">{buttonSub}</div>}
          </div>
          <div className="text-white/60">▾</div>
        </div>
      </button>

      {open && typeof window !== "undefined" && menuPos
        ? createPortal(
            <div
              id="nice-select-menu"
              role="listbox"
              className={
                menuClassName ??
                "fixed z-[12000] overflow-hidden rounded-xl border border-white/15 bg-[#0b1626] shadow-2xl"
              }
              style={{
                left: menuPos.left,
                top: menuPos.placement === "bottom" ? menuPos.top : undefined,
                bottom: menuPos.placement === "top" ? window.innerHeight - (menuPos.top - 8) : undefined,
                width: menuPos.width,
              }}
            >
              <div className="max-h-[360px] overflow-auto py-1">
                {options.map((opt, idx) => {
                  const isSelected = opt.value === value;
                  const isActive = idx === activeIndex;
                  const isDisabled = Boolean(opt.disabled);
                  return (
                    <button
                      key={String(opt.value)}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      disabled={isDisabled}
                      className={[
                        "w-full px-3 py-2 text-left text-sm",
                        isDisabled ? "opacity-50 cursor-not-allowed" : "hover:bg-cyan-300/10",
                        isSelected ? "bg-cyan-400/10 text-cyan-100" : "text-white/90",
                        isActive ? "outline outline-1 outline-cyan-400/70" : "",
                      ].join(" ")}
                      onMouseMove={() => setActiveIndex(idx)}
                      onClick={() => {
                        if (isDisabled) return;
                        onChange(opt.value);
                        setOpen(false);
                      }}
                    >
                      <div className="truncate">{opt.label}</div>
                      {opt.hint && <div className="truncate text-[11px] text-white/50">{opt.hint}</div>}
                    </button>
                  );
                })}
              </div>
            </div>,
            document.body
          )
        : null}
    </div>
  );
}

