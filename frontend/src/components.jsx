import { useState, useRef, useEffect, useCallback } from "react";

/* ──────────────────────────────────────────────────────────
   CustomSelectDropdown
   Props:
     value       : string
     onChange    : (value: string) => void
     options     : Array<{ value: string; label: string; desc?: string }>
     disabled?   : boolean
     placeholder?: string
─────────────────────────────────────────────────────────── */
export function CustomSelectDropdown({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = "Select…",
}) {
  const [open, setOpen] = useState(false);
  const [focusIdx, setFocusIdx] = useState(-1);
  const rootRef = useRef(null);
  const listRef = useRef(null);

  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    function onDown(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      const idx = options.findIndex((o) => o.value === value);
      setFocusIdx(idx >= 0 ? idx : 0);
    }
  }, [open]);

  useEffect(() => {
    if (open && listRef.current && focusIdx >= 0) {
      const item = listRef.current.children[focusIdx];
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [focusIdx, open]);

  function handleKeyDown(e) {
    if (disabled) return;
    if (!open && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) {
      e.preventDefault(); setOpen(true); return;
    }
    if (!open) return;
    if (e.key === "Escape") { setOpen(false); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx((i) => Math.min(i + 1, options.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (focusIdx >= 0 && focusIdx < options.length) { onChange(options[focusIdx].value); setOpen(false); }
    }
  }

  return (
    <div
      ref={rootRef}
      className={`csd-root${open ? " open" : ""}${disabled ? " disabled" : ""}`}
      tabIndex={disabled ? -1 : 0}
      role="combobox"
      aria-expanded={open}
      aria-haspopup="listbox"
      onKeyDown={handleKeyDown}
      onClick={() => !disabled && setOpen((v) => !v)}
    >
      <div className="csd-trigger">
        <span className={`csd-value${!selected ? " placeholder" : ""}`}>
          {selected ? selected.label : placeholder}
        </span>
        <svg className={`csd-chevron${open ? " open" : ""}`} width="12" height="12"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && (
        <ul ref={listRef} className="csd-menu" role="listbox"
          onMouseLeave={() => setFocusIdx(-1)}>
          {options.map((opt, i) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={opt.value === value}
              className={`csd-option${opt.value === value ? " selected" : ""}${i === focusIdx ? " focused" : ""}`}
              onMouseEnter={() => setFocusIdx(i)}
              onClick={(e) => { e.stopPropagation(); onChange(opt.value); setOpen(false); }}
            >
              <div className="csd-option-text">
                <span className="csd-option-label">{opt.label}</span>
                {opt.desc && <span className="csd-option-desc">{opt.desc}</span>}
              </div>
              {opt.value === value && (
                <svg className="csd-check" width="12" height="12" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


/* ──────────────────────────────────────────────────────────
   CustomDatePicker  — fully custom React calendar, no native input
   Props:
     value       : string   (YYYY-MM-DD or "")
     onChange    : (value: string) => void
     disabled?   : boolean
     placeholder?: string
     min?        : string   (YYYY-MM-DD)
     max?        : string   (YYYY-MM-DD)
─────────────────────────────────────────────────────────── */

const DAYS   = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

function parseYMD(str) {
  if (!str) return null;
  const [y, m, d] = str.split("-").map(Number);
  return { y, m, d };
}
function toYMD(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}
function formatDisplay(str) {
  const p = parseYMD(str);
  if (!p) return "";
  const d = new Date(p.y, p.m - 1, p.d);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
function daysInMonth(y, m) {
  return new Date(y, m, 0).getDate();
}
function firstDayOfMonth(y, m) {
  return new Date(y, m - 1, 1).getDay();
}

export function CustomDatePicker({
  value,
  onChange,
  disabled = false,
  placeholder = "Pick a date",
  min,
  max,
}) {
  const today = new Date();
  const todayYMD = toYMD(today.getFullYear(), today.getMonth() + 1, today.getDate());

  const initFromValue = () => {
    const p = parseYMD(value);
    if (p) return { y: p.y, m: p.m };
    return { y: today.getFullYear(), m: today.getMonth() + 1 };
  };

  const [open, setOpen] = useState(false);
  const [view, setView] = useState(initFromValue);
  const rootRef = useRef(null);

  // Sync view month/year when value changes externally
  useEffect(() => {
    if (value) {
      const p = parseYMD(value);
      if (p) setView({ y: p.y, m: p.m });
    }
  }, [value]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onDown(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function prevMonth() {
    setView(({ y, m }) => m === 1 ? { y: y - 1, m: 12 } : { y, m: m - 1 });
  }
  function nextMonth() {
    setView(({ y, m }) => m === 12 ? { y: y + 1, m: 1 } : { y, m: m + 1 });
  }

  function isDisabled(dayStr) {
    if (min && dayStr < min) return true;
    if (max && dayStr > max) return true;
    return false;
  }

  function handleDayClick(dayStr) {
    if (isDisabled(dayStr)) return;
    onChange(dayStr);
    setOpen(false);
  }

  // Build calendar grid
  const firstDay = firstDayOfMonth(view.y, view.m);
  const totalDays = daysInMonth(view.y, view.m);
  const prevDays  = daysInMonth(view.y, view.m === 1 ? 12 : view.m - 1);

  const cells = [];
  // Leading filler from previous month
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: prevDays - i, cur: false });
  }
  // Current month days
  for (let d = 1; d <= totalDays; d++) {
    cells.push({ day: d, cur: true });
  }
  // Trailing filler
  let trail = 1;
  while (cells.length % 7 !== 0) {
    cells.push({ day: trail++, cur: false });
  }

  return (
    <div
      ref={rootRef}
      className={`cdp-root${disabled ? " disabled" : ""}${value ? " has-value" : ""}`}
    >
      {/* ── Trigger button ── */}
      <button
        type="button"
        className="cdp-trigger"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
      >
        <svg className="cdp-icon" width="13" height="13" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8"  y1="2" x2="8"  y2="6" />
          <line x1="3"  y1="10" x2="21" y2="10" />
        </svg>
        <span className={`cdp-display${!value ? " placeholder" : ""}`}>
          {value ? formatDisplay(value) : placeholder}
        </span>
        {value && (
          <span
            className="cdp-clear"
            role="button"
            tabIndex={0}
            aria-label="Clear date"
            onClick={(e) => { e.stopPropagation(); onChange(""); }}
            onKeyDown={(e) => e.key === "Enter" && (e.stopPropagation(), onChange(""))}
          >
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6"  y1="6" x2="18" y2="18" />
            </svg>
          </span>
        )}
      </button>

      {/* ── Calendar panel ── */}
      {open && (
        <div className="cdp-panel" role="dialog" aria-label="Calendar">
          {/* Header: prev / Month Year / next */}
          <div className="cdp-header">
            <button type="button" className="cdp-nav" onClick={prevMonth} aria-label="Previous month">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <span className="cdp-month-label">
              {MONTHS[view.m - 1]} {view.y}
            </span>
            <button type="button" className="cdp-nav" onClick={nextMonth} aria-label="Next month">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          </div>

          {/* Day-of-week headers */}
          <div className="cdp-grid">
            {DAYS.map((d) => (
              <div key={d} className="cdp-dow">{d}</div>
            ))}

            {/* Day cells */}
            {cells.map((cell, i) => {
              if (!cell.cur) {
                return <div key={`f${i}`} className="cdp-day filler">{cell.day}</div>;
              }
              const dayStr    = toYMD(view.y, view.m, cell.day);
              const isToday   = dayStr === todayYMD;
              const isSelected = dayStr === value;
              const isDis     = isDisabled(dayStr);

              return (
                <button
                  key={dayStr}
                  type="button"
                  className={[
                    "cdp-day",
                    isSelected ? "selected" : "",
                    isToday    ? "today"    : "",
                    isDis      ? "disabled" : "",
                  ].filter(Boolean).join(" ")}
                  disabled={isDis}
                  onClick={() => handleDayClick(dayStr)}
                  aria-label={dayStr}
                  aria-pressed={isSelected}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>

          {/* Footer: Clear / Today */}
          <div className="cdp-footer">
            <button
              type="button"
              className="cdp-footer-btn"
              onClick={() => { onChange(""); setOpen(false); }}
            >
              Clear
            </button>
            <button
              type="button"
              className="cdp-footer-btn accent"
              disabled={isDisabled(todayYMD)}
              onClick={() => { onChange(todayYMD); setOpen(false); }}
            >
              Today
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
