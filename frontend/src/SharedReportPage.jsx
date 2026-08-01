import { useState, useEffect } from "react";
import { fetchPublicReport } from "./api";

/**
 * SharedReportPage — clean, read-only public view of a shared Synthis report.
 *
 * Accessed at /shared/:token (no auth required).
 * Renders the same citations/sections/sources as the authenticated view
 * but with NONE of the editing, annotation, follow-up, or sharing affordances.
 * No navigation back into the authenticated app.
 */

function renderCitations(text, sources) {
  if (!text) return null;
  const parts = text.split(/(\[S\d+\])/g);
  return parts.map((part, i) => {
    if (/^\[S\d+\]$/.test(part)) {
      const sourceId = part.slice(1, -1);
      const src = sources?.find((s) => s.id === sourceId);
      return (
        <span key={i} className="inline-cite-container">
          <span className="inline-cite-hover">{part}</span>
          {src && (
            <div className="cite-popover">
              <div className="cite-popover-title">{src.title}</div>
              <div className="cite-popover-meta">
                <span className="cite-popover-domain">
                  {(() => { try { return new URL(src.url).hostname; } catch { return src.url; } })()}
                </span>
                <span className={`tier-badge ${src.credibility_tier || "unrated"}`}>
                  {src.credibility_tier || "Unrated"}
                </span>
              </div>
              {src.snippet && (
                <div className="cite-popover-snippet">{src.snippet.slice(0, 180)}…</div>
              )}
              <a href={src.url} target="_blank" rel="noopener noreferrer" className="cite-popover-link">
                Open source ↗
              </a>
            </div>
          )}
        </span>
      );
    }
    return part;
  });
}

export default function SharedReportPage({ token }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    if (!token) { setError("No share token provided."); setLoading(false); return; }
    fetchPublicReport(token)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
        <div style={{ textAlign: "center" }}>
          <div className="spinner" style={{ margin: "0 auto 16px" }} />
          <div style={{ color: "var(--text-2)", fontSize: 14 }}>Loading shared report…</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
        <div style={{ textAlign: "center", maxWidth: 420, padding: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
          <h2 style={{ color: "var(--text-1)", marginBottom: 8, fontSize: 20 }}>Report Unavailable</h2>
          <p style={{ color: "var(--text-3)", fontSize: 14 }}>{error}</p>
          <p style={{ color: "var(--text-3)", fontSize: 12, marginTop: 16 }}>
            This report may have been unshared by its owner, or the link may be invalid.
          </p>
        </div>
      </div>
    );
  }

  const sourceCount = report?.sources?.length ?? 0;
  const takeawayCount = report?.key_takeaways?.length ?? 0;
  const sectionCount = report?.sections?.length ?? 0;

  return (
    <div className="app" style={{ minHeight: "100vh" }}>
      {/* ── Shared Report Header ─────────────────────────────────────── */}
      <header className="header" style={{ justifyContent: "space-between" }}>
        <div className="header-logo" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" fill="url(#sg)" opacity="0.15"/>
            <path d="M10 22 C10 16, 16 10, 22 10" stroke="url(#sg)" strokeWidth="2.5" strokeLinecap="round"/>
            <path d="M10 22 C14 22, 18 18, 22 10" stroke="url(#sg)" strokeWidth="2.5" strokeLinecap="round"/>
            <defs>
              <linearGradient id="sg" x1="0" y1="0" x2="32" y2="32">
                <stop stopColor="#7c6af0"/>
                <stop offset="1" stopColor="#38bdf8"/>
              </linearGradient>
            </defs>
          </svg>
          Synthis
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{
            fontSize: 11, fontWeight: 600, color: "var(--accent)",
            background: "rgba(124,106,240,0.12)", borderRadius: 6,
            padding: "3px 10px", border: "1px solid rgba(124,106,240,0.2)",
            letterSpacing: "0.04em", textTransform: "uppercase"
          }}>
            Shared Report · Read Only
          </span>
        </div>
      </header>

      {/* ── Report Card ──────────────────────────────────────────────── */}
      <main className="main">
        <div className="report-card">
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
            {/* No action buttons on shared view — no edit/annotate/share/download */}
          </div>

          {/* Confidence note */}
          {report.confidence_note && (
            <div className="confidence-note" style={{ margin: "0 24px 4px" }}>
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}>
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              <div>{report.confidence_note}</div>
            </div>
          )}

          {/* Tabs */}
          <div className="tabs">
            {["overview", "sources"].map((tab) => (
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
                {/* Key Takeaways */}
                {report.key_takeaways?.length > 0 && (
                  <>
                    <div className="label">Key Takeaways</div>
                    <div className="takeaways">
                      {report.key_takeaways.map((kt, i) => (
                        <div key={i} className="takeaway-item">
                          <div className="takeaway-bullet" />
                          <div style={{ flex: 1 }}>
                            <div className="takeaway-text">{kt.text}</div>
                            <div className="takeaway-sources" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                              {kt.corroboration_count >= 2 ? (
                                <span className="corrob-badge multi">Corroborated by {kt.corroboration_count} sources</span>
                              ) : (
                                <span className="corrob-badge single">Single-sourced</span>
                              )}
                              {kt.source_ids.map((sid) => (
                                <span key={sid} className="source-badge">{sid}</span>
                              ))}
                            </div>
                            {/* No follow-up or annotation affordances on shared view */}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* Conflicting Information */}
                {report.conflicting_information?.length > 0 && (
                  <div style={{ marginTop: 24, marginBottom: 28 }}>
                    <div className="label">⚠️ Conflicting Information &amp; Disagreements</div>
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

                {/* Report Sections */}
                {report.sections?.length > 0 && (
                  <>
                    <div className="label" style={{ marginTop: 24 }}>Report Sections</div>
                    {report.sections.map((sec, i) => (
                      <div key={i} className="section-block">
                        <div className="section-heading">{sec.heading}</div>
                        <div className="section-content">
                          {renderCitations(sec.content, report.sources)}
                        </div>
                        {/* No follow-up or annotation affordances */}
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
                        <a className="source-url" href={src.url} target="_blank" rel="noopener noreferrer">
                          {src.url}
                        </a>
                        {src.summary && <div className="source-summary">{src.summary}</div>}
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                          {src.relevance_score != null && (
                            <span className="source-score">
                              Relevance: {(src.relevance_score * 100).toFixed(0)}%
                            </span>
                          )}
                          <span className={`tier-badge ${src.credibility_tier || "unrated"}`}>
                            {src.credibility_tier === "primary" ? "Primary"
                              : src.credibility_tier === "secondary" ? "Secondary"
                              : src.credibility_tier === "low-authority" ? "Low Authority"
                              : "Unrated"}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer attribution — no nav back into app */}
        <div style={{ textAlign: "center", paddingTop: 32, paddingBottom: 40, color: "var(--text-3)", fontSize: 12 }}>
          Research generated by{" "}
          <span style={{ color: "var(--accent)", fontWeight: 600 }}>Synthis</span>
          {" "}· Grounded, cited, reliable
        </div>
      </main>
    </div>
  );
}
