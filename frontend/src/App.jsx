import { useState, useEffect, useRef } from "react";
import "./index.css";
import { checkHealth, runResearch, fetchReports, fetchReportByFilename } from "./api";
import { CustomSelectDropdown, CustomDatePicker } from "./components";

const STAGES = [
  { id: 1, label: "Planning search queries with Gemini" },
  { id: 2, label: "Retrieving web sources via Tavily" },
  { id: 3, label: "Filtering and deduplicating sources" },
  { id: 4, label: "Summarizing each source" },
  { id: 5, label: "Synthesizing report and takeaways" },
  { id: 6, label: "Mapping and validating citations" },
];

const EXAMPLE_TOPICS = [
  "Solid state battery technology 2026",
  "AI agents in software engineering",
  "mRNA vaccine technology advances",
  "Fusion energy latest breakthroughs",
];

const DEPTH_OPTIONS = [
  { id: "quick", label: "Quick Scan", desc: "2 queries · 6 sources" },
  { id: "standard", label: "Standard", desc: "4 queries · 12 sources" },
  { id: "deep", label: "Deep Research", desc: "6 queries · 20 sources" },
];

const DATE_FILTER_OPTIONS = [
  { value: "any", label: "Any time" },
  { value: "past_year", label: "Past year" },
  { value: "past_5_years", label: "Past 5 years" },
  { value: "custom", label: "Custom range…" },
];

const DOMAIN_MODE_OPTIONS = [
  { value: "none", label: "Off", desc: "Search all domains" },
  { value: "include", label: "Include only", desc: "Restrict to listed domains" },
  { value: "exclude", label: "Exclude", desc: "Block listed domains" },
];

const SOURCE_CATEGORY_OPTIONS = [
  { value: "general", label: "General" },
  { value: "news", label: "News" },
  { value: "finance", label: "Finance" },
];

export default function App() {
  const [topic, setTopic] = useState("");
  const [depth, setDepth] = useState("standard");
  const [loading, setLoading] = useState(false);
  const [stageIdx, setStageIdx] = useState(-1);
  const [report, setReport] = useState(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [copied, setCopied] = useState(false);
  const [health, setHealth] = useState(null);

  // Advanced filter states
  const [dateFilter, setDateFilter] = useState("any");
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");
  const [domainMode, setDomainMode] = useState("none");
  const [domainList, setDomainList] = useState([]);
  const [domainInput, setDomainInput] = useState("");
  const [sourceCategory, setSourceCategory] = useState("general");
  const [showFilterPanel, setShowFilterPanel] = useState(false);

  // Advanced feature states
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showDrawer, setShowDrawer] = useState(false);
  const [historyReports, setHistoryReports] = useState([]);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));
  }, []);

  // Stage animation timing adjusts based on depth
  useEffect(() => {
    if (!loading) { setStageIdx(-1); return; }
    setStageIdx(0);
    const delay = depth === "quick" ? 3000 : depth === "deep" ? 7000 : 5000;
    const timers = STAGES.map((_, i) =>
      setTimeout(() => setStageIdx(i), i * delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading, depth]);

  // Clean up speech synthesis on unmount
  useEffect(() => {
    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  function handleAddDomain(e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = domainInput.trim().toLowerCase();
      if (val && !domainList.includes(val)) {
        setDomainList([...domainList, val]);
        setDomainInput("");
      }
    }
  }

  function handleRemoveDomain(d) {
    setDomainList(domainList.filter((item) => item !== d));
  }

  async function handleSubmit(e) {
    e?.preventDefault();
    if (!topic.trim() || loading) return;
    setError(null);
    setReport(null);
    setMarkdown("");
    setLoading(true);
    setActiveTab("overview");
    stopAudio();

    const filterSettings = {
      date_filter: dateFilter,
      custom_start_date: dateFilter === "custom" ? customStartDate : null,
      custom_end_date: dateFilter === "custom" ? customEndDate : null,
      domain_mode: domainMode,
      domain_list: domainList,
      source_category: sourceCategory,
    };

    try {
      const data = await runResearch(topic.trim(), depth, filterSettings);
      setReport(data.report);
      setMarkdown(data.markdown || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${topic.slice(0, 30).replace(/\s+/g, "_")}_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handlePrint() {
    window.print();
  }

  // Speech Audio Narration for Takeaways
  function toggleAudioSummary() {
    if (!window.speechSynthesis) return;

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    if (!report?.key_takeaways?.length) return;

    const textToRead = report.key_takeaways.map((t) => t.text).join(". ");
    const utterance = new SpeechSynthesisUtterance(textToRead);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  }

  function stopAudio() {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }

  // Open Past Reports Drawer
  async function handleOpenHistory() {
    setShowDrawer(true);
    try {
      const list = await fetchReports();
      setHistoryReports(list);
    } catch (err) {
      console.error(err);
    }
  }

  // Load a past report from history
  async function handleSelectHistoryReport(filename) {
    setShowDrawer(false);
    setLoading(true);
    setError(null);
    try {
      const res = await fetchReportByFilename(filename);
      setMarkdown(res.markdown);

      // Parse markdown basic metadata to populate UI
      setReport({
        topic: filename.replace(/^report_/, "").replace(/\.md$/, "").replace(/_/g, " "),
        generated_at: "Saved Report",
        key_takeaways: [],
        sections: [{ heading: "Full Research Report", content: res.markdown }],
        sources: [],
      });
      setActiveTab("markdown");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Interactive inline citation renderer with hover card popovers
  function renderInteractiveCitations(text) {
    const parts = text.split(/(\[S\d+\])/g);
    return parts.map((part, i) => {
      if (/^\[S\d+\]$/.test(part)) {
        const sourceId = part.slice(1, -1);
        const sourceObj = report?.sources?.find((s) => s.id === sourceId);

        return (
          <span key={i} className="inline-cite-container">
            <span className="inline-cite-hover">{part}</span>
            {sourceObj && (
              <div className="cite-popover">
                <div className="cite-popover-title">{sourceObj.title}</div>
                <div className="cite-popover-meta">
                  <span className="cite-popover-domain">{new URL(sourceObj.url).hostname}</span>
                  <span className={`tier-badge ${sourceObj.credibility_tier || "unrated"}`}>
                    {sourceObj.credibility_tier === "primary"
                      ? "Primary"
                      : sourceObj.credibility_tier === "secondary"
                      ? "Secondary"
                      : sourceObj.credibility_tier === "low-authority"
                      ? "Low Authority"
                      : "Unrated"}
                  </span>
                </div>
                <div className="cite-popover-snippet">{sourceObj.snippet || sourceObj.summary}</div>
              </div>
            )}
          </span>
        );
      }
      return part;
    });
  }

  const sourceCount = report?.sources?.length ?? 0;
  const takeawayCount = report?.key_takeaways?.length ?? 0;
  const sectionCount = report?.sections?.length ?? 0;

  const filtersActive = dateFilter !== "any" || domainMode !== "none" || sourceCategory !== "general";

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-logo">
          Synthis
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="action-btn" onClick={handleOpenHistory}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            Past Reports
          </button>
          {health && (
            <span
              className={`status-dot ${health.status === "healthy" &&
                  health.tavily_configured &&
                  health.gemini_configured
                  ? "ok"
                  : "warn"
                }`}
            />
          )}
          <span className="header-badge">Research AI</span>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-eyebrow">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <circle cx="5" cy="5" r="5" />
          </svg>
          Grounded · Cited · Reliable
        </div>
        <h1>
          Research anything,<br />
          <span>cited from the web</span>
        </h1>
        <p>
          Enter a topic and get a structured research report every claim traced
          back to a live Tavily-retrieved source. Zero hallucinations.
        </p>
      </section>

      {/* ── Search Card ── */}
      <div className="search-card">
        {/* Health status bar */}
        {health && (
          <div className="status-bar" style={{ paddingLeft: 0, marginBottom: 12 }}>
            <span
              className={`status-dot ${health.status === "healthy" &&
                  health.tavily_configured &&
                  health.gemini_configured
                  ? "ok"
                  : "warn"
                }`}
            />
            <span>
              {health.status === "healthy" &&
                health.tavily_configured &&
                health.gemini_configured
                ? `Backend connected · Model: ${health.model}`
                : "Backend connected — check API keys in .env"}
            </span>
          </div>
        )}

        <form className="search-box" onSubmit={handleSubmit}>
          <div className="search-row">
            <textarea
              className="search-textarea"
              placeholder="Enter a research topic… e.g. 'Solid state batteries 2026'"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              maxLength={400}
              disabled={loading}
            />
            <button className="search-btn" type="submit" disabled={!topic.trim() || loading}>
              {loading ? (
                <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Researching…</>
              ) : (
                <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg> Research</>
              )}
            </button>
          </div>

          <div className="search-footer">
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="search-hint">Enter to submit · Shift+Enter for new line</span>

              {/* Depth selector */}
              <div className="depth-selector">
                {DEPTH_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    className={`depth-btn${depth === opt.id ? " active" : ""}`}
                    onClick={() => setDepth(opt.id)}
                    disabled={loading}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              {/* Filter Panel Toggle */}
              <button
                type="button"
                className={`filter-toggle-btn${showFilterPanel || filtersActive ? " active" : ""}`}
                onClick={() => setShowFilterPanel(!showFilterPanel)}
                disabled={loading}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
                </svg>
                Filters {filtersActive ? "• Active" : ""}
              </button>
            </div>

            <span className={`char-counter${topic.length > 340 ? " warn" : ""}`}>
              {topic.length}/400
            </span>
          </div>

          {/* Expandable Filter Panel */}
          {showFilterPanel && (
            <div className="filter-panel">
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>

                {/* Date range filter */}
                <div className="filter-group" style={{ flex: 1, minWidth: 180 }}>
                  <label className="filter-label"> Date Range</label>
                  <CustomSelectDropdown
                    value={dateFilter}
                    onChange={setDateFilter}
                    options={DATE_FILTER_OPTIONS}
                    disabled={loading}
                  />
                  {dateFilter === "custom" && (
                    <div className="date-custom-row">
                      <CustomDatePicker
                        value={customStartDate}
                        onChange={setCustomStartDate}
                        placeholder="Start date"
                        max={customEndDate || undefined}
                        disabled={loading}
                      />
                      <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>to</span>
                      <CustomDatePicker
                        value={customEndDate}
                        onChange={setCustomEndDate}
                        placeholder="End date"
                        min={customStartDate || undefined}
                        disabled={loading}
                      />
                    </div>
                  )}
                </div>

                {/* Domain filter */}
                <div className="filter-group" style={{ flex: 1, minWidth: 200 }}>
                  <label className="filter-label"> Domain Filter</label>
                  <CustomSelectDropdown
                    value={domainMode}
                    onChange={setDomainMode}
                    options={DOMAIN_MODE_OPTIONS}
                    disabled={loading}
                  />
                  {domainMode !== "none" && (
                    <input
                      type="text"
                      className="filter-input"
                      placeholder="e.g. arxiv.org, nature.com (Enter to add)"
                      value={domainInput}
                      onChange={(e) => setDomainInput(e.target.value)}
                      onKeyDown={handleAddDomain}
                      disabled={loading}
                    />
                  )}
                  {domainMode !== "none" && domainList.length > 0 && (
                    <div className="domain-tags">
                      {domainList.map((d) => (
                        <span key={d} className="domain-tag">
                          {d}
                          <button
                            type="button"
                            className="domain-tag-remove"
                            onClick={() => handleRemoveDomain(d)}
                          >
                            ✕
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Source Category */}
                <div className="filter-group" style={{ width: 160 }}>
                  <label className="filter-label"> Topic Scope</label>
                  <CustomSelectDropdown
                    value={sourceCategory}
                    onChange={setSourceCategory}
                    options={SOURCE_CATEGORY_OPTIONS}
                    disabled={loading}
                  />
                </div>

              </div>
            </div>
          )}
        </form>

        {/* Example chips */}
        {!loading && !report && (
          <div className="chips" style={{ marginTop: 14 }}>
            {EXAMPLE_TOPICS.map((t) => (
              <button key={t} className="chip" onClick={() => setTopic(t)}>
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><polyline points="9 18 15 12 9 6" /></svg>
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Main Content ── */}
      <main className="main">
        {/* Progress stages */}
        {loading && (
          <div className="progress-card">
            <div className="progress-header">
              <div className="spinner" />
              <div>
                <div className="progress-title">Generating research report ({depth} mode)…</div>
                <div className="progress-topic">{topic}</div>
              </div>
            </div>
            <div className="stages">
              {STAGES.map((stage, i) => {
                const state =
                  i < stageIdx ? "done" : i === stageIdx ? "active" : "pending";
                return (
                  <div key={stage.id} className="stage-row">
                    <div className={`stage-icon ${state}`}>
                      {state === "done" ? "✓" : stage.id}
                    </div>
                    <span className={`stage-label ${state}`}>{stage.label}</span>
                    {state === "active" && (
                      <div className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5, marginLeft: 4 }} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="error-card">
            <div className="error-title">Research failed</div>
            <div className="error-msg">{error}</div>
          </div>
        )}

        {/* Report */}
        {report && !loading && (
          <div className="report-card">
            {/* Filter Summary Chips */}
            {report.filter_settings && (
              <div className="filter-summary-row" style={{ padding: "14px 24px 0" }}>
                <span className="filter-summary-chip">
                  <span className="icon">📅</span>
                  {report.filter_settings.date_filter === "past_year"
                    ? "Past year"
                    : report.filter_settings.date_filter === "past_5_years"
                      ? "Past 5 years"
                      : report.filter_settings.date_filter === "custom"
                        ? `Custom: ${report.filter_settings.custom_start_date || "?"} to ${report.filter_settings.custom_end_date || "?"}`
                        : "Any time"}
                </span>

                {report.filter_settings.domain_mode !== "none" && report.filter_settings.domain_list?.length > 0 && (
                  <span className="filter-summary-chip">
                    <span className="icon">🌐</span>
                    {report.filter_settings.domain_mode === "include" ? "Only: " : "Exclude: "}
                    {report.filter_settings.domain_list.join(", ")}
                  </span>
                )}

                {report.filter_settings.source_category && report.filter_settings.source_category !== "general" && (
                  <span className="filter-summary-chip">
                    <span className="icon">📰</span>
                    {report.filter_settings.source_category.toUpperCase()} scope
                  </span>
                )}
              </div>
            )}

            {/* Report header */}
            <div className="report-header">
              <div>
                <div className="report-title">{report.topic}</div>
                <div className="report-meta">
                  {sourceCount > 0 && <>{sourceCount} sources · </>}
                  {takeawayCount > 0 && <>{takeawayCount} takeaways · </>}
                  {sectionCount} sections · {report.generated_at}
                </div>
              </div>
              <div className="report-actions">
                {/* Audio speech button */}
                {report.key_takeaways?.length > 0 && (
                  <button className="action-btn" onClick={toggleAudioSummary}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
                    </svg>
                    {isSpeaking ? "Stop Audio" : "Listen Summary"}
                  </button>
                )}

                <button className="action-btn" onClick={handlePrint}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polyline points="6 9 6 2 18 2 18 9" />
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                    <rect x="6" y="14" width="12" height="8" />
                  </svg>
                  Print
                </button>

                <button className={`action-btn${copied ? " success" : ""}`} onClick={handleCopy}>
                  {copied ? (
                    <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><polyline points="20 6 9 17 4 12" /></svg> Copied</>
                  ) : (
                    <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg> Copy MD</>
                  )}
                </button>
                <button className="action-btn" onClick={handleDownload}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                  Download
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="tabs">
              {["overview", "sources", "markdown"].map((tab) => (
                <button
                  key={tab}
                  className={`tab-btn${activeTab === tab ? " active" : ""}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  {tab === "sources" && sourceCount > 0 && <> ({sourceCount})</>}
                </button>
              ))}
            </div>

            <div className="report-body">
              {/* Overview tab */}
              {activeTab === "overview" && (
                <>
                  {report.confidence_note && (
                    <div className="confidence-note">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
                      {report.confidence_note}
                    </div>
                  )}

                  {/* Key takeaways */}
                  {report.key_takeaways?.length > 0 && (
                    <>
                      <div className="label">Key Takeaways</div>
                      <div className="takeaways">
                        {report.key_takeaways.map((kt, i) => (
                          <div key={i} className="takeaway-item">
                            <div className="takeaway-bullet" />
                            <div>
                              <div className="takeaway-text">{kt.text}</div>
                                <div className="takeaway-sources" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                                  {kt.corroboration_count >= 2 ? (
                                    <span className="corrob-badge multi">
                                      Corroborated by {kt.corroboration_count} sources
                                    </span>
                                  ) : (
                                    <span className="corrob-badge single">
                                      Single-sourced
                                    </span>
                                  )}
                                  {kt.source_ids.map((sid) => (
                                    <span key={sid} className="source-badge">{sid}</span>
                                  ))}
                                </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* Conflicting Information Card */}
                  {report.conflicting_information?.length > 0 && (
                    <div style={{ marginTop: 24, marginBottom: 28 }}>
                      <div className="label">⚠️ Conflicting Information & Disagreements</div>
                      <div className="conflict-list">
                        {report.conflicting_information.map((item, idx) => (
                          <div key={idx} className="conflict-card">
                            <div className="conflict-topic">Disputed: {item.topic}</div>
                            <div className="conflict-positions">
                              {item.positions?.map((pos, pIdx) => (
                                <div key={pIdx} className="conflict-position">
                                  <div className="conflict-claim">{pos.claim}</div>
                                  <div className="conflict-sources">
                                    {pos.source_ids?.map((sid) => (
                                      <span key={sid} className="source-badge">{sid}</span>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Report sections */}
                  {report.sections?.length > 0 && (
                    <>
                      <div className="label" style={{ marginTop: 24 }}>Report Sections</div>
                      {report.sections.map((sec, i) => (
                        <div key={i} className="section-block">
                          <div className="section-heading">{sec.heading}</div>
                          <div className="section-content">
                            {renderInteractiveCitations(sec.content)}
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </>
              )}

              {/* Sources tab */}
              {activeTab === "sources" && (
                <>
                  <div className="label">Retrieved Sources</div>
                  <div className="sources-list">
                    {report.sources?.map((src) => (
                      <div key={src.id} className="source-item">
                        <span className="source-id">{src.id}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="source-title">{src.title}</div>
                          <a
                            className="source-url"
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {src.url}
                          </a>
                          {src.summary && (
                            <div className="source-summary">{src.summary}</div>
                          )}
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                            {src.relevance_score != null && (
                              <span className="source-score">
                                Relevance: {(src.relevance_score * 100).toFixed(0)}%
                              </span>
                            )}
                            <span className={`tier-badge ${src.credibility_tier || "unrated"}`}>
                              {src.credibility_tier === "primary"
                                ? "Primary"
                                : src.credibility_tier === "secondary"
                                ? "Secondary"
                                : src.credibility_tier === "low-authority"
                                ? "Low Authority"
                                : "Unrated"}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* Markdown tab */}
              {activeTab === "markdown" && (
                <>
                  <div className="label">Raw Markdown</div>
                  <pre className="markdown-view">{markdown}</pre>
                </>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && !report && (
          <div className="empty-state">
            <div className="empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1} strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <h3>Enter a topic to begin</h3>
            <p>Your structured, cited research report will appear here.</p>
          </div>
        )}
      </main>

      {/* ── Slide-out History Drawer ── */}
      {showDrawer && (
        <div className="drawer-overlay" onClick={() => setShowDrawer(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title">Past Research Reports</div>
              <button className="close-btn" onClick={() => setShowDrawer(false)}>✕</button>
            </div>
            <div className="history-list">
              {historyReports.length === 0 ? (
                <div style={{ fontSize: 13, color: "var(--text-3)", textAlign: "center", paddingTop: 40 }}>
                  No saved reports found on server.
                </div>
              ) : (
                historyReports.map((item) => (
                  <div
                    key={item.filename}
                    className="history-item"
                    onClick={() => handleSelectHistoryReport(item.filename)}
                  >
                    <div className="history-name">{item.filename}</div>
                    <div className="history-meta">
                      {(item.size_bytes / 1024).toFixed(1)} KB
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
