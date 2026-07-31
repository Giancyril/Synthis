import { useState, useEffect } from "react";
import "./index.css";
import { checkHealth, runResearch } from "./api";

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
  "Quantum computing commercial applications",
  "mRNA vaccine technology advances",
  "Fusion energy latest breakthroughs",
];

function renderInlineCitations(text) {
  const parts = text.split(/(\[S\d+\])/g);
  return parts.map((part, i) =>
    /^\[S\d+\]$/.test(part) ? (
      <span key={i} className="inline-cite">{part}</span>
    ) : (
      part
    )
  );
}

export default function App() {
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [stageIdx, setStageIdx] = useState(-1);
  const [report, setReport] = useState(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [copied, setCopied] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));
  }, []);

  // Simulate progressive stage reveal during loading
  useEffect(() => {
    if (!loading) { setStageIdx(-1); return; }
    setStageIdx(0);
    const timers = STAGES.map((_, i) =>
      setTimeout(() => setStageIdx(i), i * 5200)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  async function handleSubmit(e) {
    e?.preventDefault();
    if (!topic.trim() || loading) return;
    setError(null);
    setReport(null);
    setMarkdown("");
    setLoading(true);
    setActiveTab("overview");
    try {
      const data = await runResearch(topic.trim());
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

  const sourceCount = report?.sources?.length ?? 0;
  const takeawayCount = report?.key_takeaways?.length ?? 0;
  const sectionCount = report?.sections?.length ?? 0;

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-logo">
          <div className="dot" />
          Synthis
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {health && (
            <span className="status-dot" style={{ marginRight: 4 }}
              data-status={health.status === "healthy" && health.tavily_configured && health.gemini_configured ? "ok" : "warn"}
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
          Enter a topic and get a structured research report — every claim traced
          back to a live Tavily-retrieved source. Zero hallucinations.
        </p>
      </section>

      {/* ── Search Card ── */}
      <div className="search-card">
        {/* Health status bar */}
        {health && (
          <div className="status-bar" style={{ paddingLeft: 0, marginBottom: 12 }}>
            <span
              className={`status-dot ${
                health.status === "healthy" &&
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
                <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg> Research</>
              )}
            </button>
          </div>
          <div className="search-footer">
            <span className="search-hint">Enter to submit · Shift+Enter for new line</span>
            <span className={`char-counter${topic.length > 340 ? " warn" : ""}`}>
              {topic.length}/400
            </span>
          </div>
        </form>

        {/* Example chips */}
        {!loading && !report && (
          <div className="chips" style={{ marginTop: 14 }}>
            {EXAMPLE_TOPICS.map((t) => (
              <button key={t} className="chip" onClick={() => setTopic(t)}>
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><polyline points="9 18 15 12 9 6"/></svg>
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
                <div className="progress-title">Generating research report…</div>
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
            {/* Report header */}
            <div className="report-header">
              <div>
                <div className="report-title">{report.topic}</div>
                <div className="report-meta">
                  {sourceCount} sources · {takeawayCount} takeaways · {sectionCount} sections · {report.generated_at}
                </div>
              </div>
              <div className="report-actions">
                <button className={`action-btn${copied ? " success" : ""}`} onClick={handleCopy}>
                  {copied ? (
                    <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg> Copied</>
                  ) : (
                    <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy MD</>
                  )}
                </button>
                <button className="action-btn" onClick={handleDownload}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
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
                  {tab === "sources" && <> ({sourceCount})</>}
                </button>
              ))}
            </div>

            <div className="report-body">
              {/* Overview tab */}
              {activeTab === "overview" && (
                <>
                  {report.confidence_note && (
                    <div className="confidence-note">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
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
                              {kt.source_ids?.length > 0 && (
                                <div className="takeaway-sources">
                                  {kt.source_ids.map((sid) => (
                                    <span key={sid} className="source-badge">{sid}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* Report sections */}
                  {report.sections?.length > 0 && (
                    <>
                      <div className="label" style={{ marginTop: 24 }}>Report Sections</div>
                      {report.sections.map((sec, i) => (
                        <div key={i} className="section-block">
                          <div className="section-heading">{sec.heading}</div>
                          <div className="section-content">
                            {renderInlineCitations(sec.content)}
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
                          {src.relevance_score != null && (
                            <div className="source-score">
                              Relevance: {(src.relevance_score * 100).toFixed(0)}%
                            </div>
                          )}
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
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </div>
            <h3>Enter a topic to begin</h3>
            <p>Your structured, cited research report will appear here.</p>
          </div>
        )}
      </main>
    </div>
  );
}
