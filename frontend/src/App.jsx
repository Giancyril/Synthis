import { useState, useEffect, useRef } from "react";
import "./index.css";
import {
  checkHealth,
  runResearch,
  fetchReports,
  fetchReportByFilename,
  executeFollowUpQuery,
  runComparativeResearch,
  continueResearchSession,
  shareReport,
  unshareReport,
  fetchAnnotations,
  createAnnotation,
  patchAnnotation,
  deleteAnnotation,
  searchReports,
  fetchBibliography,
  fetchDiff,
} from "./api";
import { CustomSelectDropdown, CustomDatePicker } from "./components";

const STAGES = [
  { id: 1, label: "Planning search queries with Gemini" },
  { id: 2, label: "Retrieving web sources via Tavily" },
  { id: 3, label: "Filtering and deduplicating sources" },
  { id: 4, label: "Summarizing each source" },
  { id: 5, label: "Synthesizing report and takeaways" },
  { id: 6, label: "Mapping and validating citations" },
];

const CMP_STAGES = [
  { id: 1, label: "Inferring comparison dimensions for Topic A vs B" },
  { id: 2, label: "Executing batched retrieval for both topics" },
  { id: 3, label: "Filtering and deduplicating web sources" },
  { id: 4, label: "Summarizing per-source content with Gemini" },
  { id: 5, label: "Synthesizing side-by-side comparative analysis" },
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

const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish (Español)" },
  { value: "fr", label: "French (Français)" },
  { value: "de", label: "German (Deutsch)" },
  { value: "ja", label: "Japanese (日本語)" },
  { value: "zh", label: "Chinese (中文)" },
  { value: "ar", label: "Arabic (العربية)" },
  { value: "pt", label: "Portuguese (Português)" },
  { value: "hi", label: "Hindi (हिन्दी)" },
];

export default function App() {
  const [topic, setTopic] = useState("");
  const [topicB, setTopicB] = useState("");
  const [compareMode, setCompareMode] = useState(false);
  const [compareReport, setCompareReport] = useState(null);
  const [depth, setDepth] = useState("standard");
  const [outputLanguage, setOutputLanguage] = useState("en");
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

  const [activeFollowUpTarget, setActiveFollowUpTarget] = useState(null); // { type: "takeaway"|"section", id: string }
  const [followUpQuestion, setFollowUpQuestion] = useState("");
  const [followUpLoading, setFollowUpLoading] = useState(false);

  async function handleExecuteFollowUp(type, id, questionOverride) {
    const q = questionOverride || followUpQuestion;
    if (!q || !q.trim() || followUpLoading || !report) return;

    setFollowUpLoading(true);
    try {
      const res = await executeFollowUpQuery(report, type, String(id), q.trim());
      if (res.result) {
        setReport((prev) => ({
          ...prev,
          follow_ups: [...(prev.follow_ups || []), res.result],
          sources: res.result.new_sources
            ? [...(prev.sources || []), ...res.result.new_sources]
            : prev.sources,
        }));
      }
      setActiveFollowUpTarget(null);
      setFollowUpQuestion("");
    } catch (err) {
      alert("Follow-up failed: " + err.message);
    } finally {
      setFollowUpLoading(false);
    }
  }

  function handleMergeFollowUp(fu) {
    if (!report) return;
    const newSection = {
      heading: `Follow-Up: ${fu.question}`,
      content: fu.summary,
    };
    setReport((prev) => ({
      ...prev,
      sections: [...(prev.sections || []), newSection],
      follow_ups: (prev.follow_ups || []).map((f) =>
        f.follow_up_id === fu.follow_up_id ? { ...f, merged_into_parent: true } : f
      ),
    }));
  }

  const [session, setSession] = useState(null);
  const [continueTarget, setContinueTarget] = useState(null);
  const [additionalContextInput, setAdditionalContextInput] = useState("");
  const [continueLoading, setContinueLoading] = useState(false);

  async function handleExecuteContinue() {
    if (!continueTarget || continueLoading) return;
    setContinueLoading(true);
    setError(null);
    try {
      const res = await continueResearchSession(
        continueTarget.filename,
        report,
        additionalContextInput.trim(),
        depth
      );
      if (res.session) {
        setSession(res.session);
        setReport({
          topic: res.session.topic,
          generated_at: res.session.last_updated_at,
          key_takeaways: res.session.merged_takeaways,
          sections: report?.sections || [{ heading: "Full Session Report", content: "Session updated with new pass." }],
          sources: res.session.merged_sources,
        });
      }
      setContinueTarget(null);
      setAdditionalContextInput("");
    } catch (err) {
      alert("Session continuation failed: " + err.message);
    } finally {
      setContinueLoading(false);
    }
  }

  // Feature 1: Share Modal States
  const [shareModalReportId, setShareModalReportId] = useState(null);
  const [shareModalData, setShareModalData] = useState(null); // { share_token, share_enabled, share_url }
  const [shareLoading, setShareLoading] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  async function handleOpenShare(reportId) {
    if (!reportId) return;
    setShareModalReportId(reportId);
    setShareModalData(null);
    setShareLoading(true);
    try {
      // Calling share endpoint acts as get or create
      const res = await shareReport(reportId);
      setShareModalData(res);
    } catch (err) {
      alert("Failed to load share settings: " + err.message);
      setShareModalReportId(null);
    } finally {
      setShareLoading(false);
    }
  }

  async function handleToggleShare() {
    if (!shareModalReportId || !shareModalData) return;
    setShareLoading(true);
    try {
      if (shareModalData.share_enabled) {
        const res = await unshareReport(shareModalReportId);
        setShareModalData((prev) => ({ ...prev, share_enabled: false }));
      } else {
        const res = await shareReport(shareModalReportId);
        setShareModalData(res);
      }
      // Refresh history list to update badge
      fetchReports().then(setHistoryReports).catch(() => {});
    } catch (err) {
      alert("Sharing action failed: " + err.message);
    } finally {
      setShareLoading(false);
    }
  }

  function handleCopyShareUrl() {
    if (!shareModalData?.share_url) return;
    navigator.clipboard.writeText(shareModalData.share_url);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }

  // Feature 2: Annotations States
  const [currentReportId, setCurrentReportId] = useState(null); // e.g. "report_solid_state"
  const [annotations, setAnnotations] = useState([]);
  const [activeAnnotationTarget, setActiveAnnotationTarget] = useState(null); // { targetType, targetId }
  const [newAnnotationBody, setNewAnnotationBody] = useState("");
  const [annotationLoading, setAnnotationLoading] = useState(false);

  // Load annotations whenever report changes
  useEffect(() => {
    if (report?.id || currentReportId) {
      const repId = report?.id || currentReportId;
      fetchAnnotations(repId)
        .then(setAnnotations)
        .catch(() => setAnnotations([]));
    } else {
      setAnnotations([]);
    }
  }, [report, currentReportId]);

  async function handleAddAnnotation(targetType, targetId) {
    if (!newAnnotationBody.trim() || annotationLoading) return;
    const repId = report?.id || currentReportId || "current_report";
    setAnnotationLoading(true);
    try {
      const ann = await createAnnotation(repId, targetType, String(targetId), newAnnotationBody.trim());
      setAnnotations((prev) => [...prev, ann]);
      setNewAnnotationBody("");
      // Refresh history list for unresolved count badge
      fetchReports().then(setHistoryReports).catch(() => {});
    } catch (err) {
      alert("Failed to add note: " + err.message);
    } finally {
      setAnnotationLoading(false);
    }
  }

  async function handleToggleResolveAnnotation(annId, currentStatus) {
    try {
      const updated = await patchAnnotation(annId, { resolved: !currentStatus });
      setAnnotations((prev) => prev.map((a) => (a.id === annId ? updated : a)));
      fetchReports().then(setHistoryReports).catch(() => {});
    } catch (err) {
      alert("Failed to update note: " + err.message);
    }
  }

  async function handleDeleteAnnotation(annId) {
    try {
      await deleteAnnotation(annId);
      setAnnotations((prev) => prev.filter((a) => a.id !== annId));
      fetchReports().then(setHistoryReports).catch(() => {});
    } catch (err) {
      alert("Failed to delete note: " + err.message);
    }
  }

  // Feature 3: Past Reports Drawer FTS Search States
  const [drawerQuery, setDrawerQuery] = useState("");
  const [drawerSearchResults, setDrawerSearchResults] = useState(null); // null when not searching
  const [drawerSearchLoading, setDrawerSearchLoading] = useState(false);

  useEffect(() => {
    if (!drawerQuery.trim()) {
      setDrawerSearchResults(null);
      return;
    }
    const timer = setTimeout(async () => {
      setDrawerSearchLoading(true);
      try {
        const results = await searchReports(drawerQuery.trim());
        setDrawerSearchResults(results);
      } catch (err) {
        console.error("FTS search error:", err);
      } finally {
        setDrawerSearchLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [drawerQuery]);

  // Output Feature 1: Bibliography Export States
  const [showBibPanel, setShowBibPanel] = useState(false);
  const [bibStyle, setBibStyle] = useState("apa");
  const [bibText, setBibText] = useState("");
  const [bibLoading, setBibLoading] = useState(false);
  const [bibCopied, setBibCopied] = useState(false);

  const handleLoadBibliography = async (styleToUse = bibStyle) => {
    const repId = report?.id || currentReportId || (report?.topic ? `report_${report.topic.slice(0, 20).toLowerCase().replace(/\s+/g, "_")}` : null);
    if (!repId) return;
    setBibLoading(true);
    try {
      const data = await fetchBibliography(repId, styleToUse);
      setBibText(data.text);
    } catch (err) {
      setBibText(`Failed to generate bibliography: ${err.message}`);
    } finally {
      setBibLoading(false);
    }
  };

  const handleToggleBibPanel = () => {
    if (!showBibPanel) {
      setShowBibPanel(true);
      handleLoadBibliography(bibStyle);
    } else {
      setShowBibPanel(false);
    }
  };

  const handleBibStyleChange = (newStyle) => {
    setBibStyle(newStyle);
    handleLoadBibliography(newStyle);
  };

  const handleCopyBib = () => {
    if (!bibText) return;
    navigator.clipboard.writeText(bibText);
    setBibCopied(true);
    setTimeout(() => setBibCopied(false), 2000);
  };

  // Output Feature 2: Report Diffing States
  const [possibleDuplicateHint, setPossibleDuplicateHint] = useState(null); // { report_id, topic, generated_at, similarity }
  const [showDiffModal, setShowDiffModal] = useState(false);
  const [diffData, setDiffData] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);

  // Advanced Feature 1: Credibility Deep-Dive States
  const [credibilityModalSource, setCredibilityModalSource] = useState(null);
  const [credibilityData, setCredibilityData] = useState(null);
  const [credibilityLoading, setCredibilityLoading] = useState(false);

  const handleOpenCredibility = async (sourceId) => {
    const repId = report?.id || currentReportId || (report?.topic ? `report_${report.topic.slice(0, 20).toLowerCase().replace(/\s+/g, "_")}` : null);
    if (!repId || !sourceId) return;
    setCredibilityModalSource(sourceId);
    setCredibilityLoading(true);
    setCredibilityData(null);
    try {
      const res = await fetchSourceCredibility(repId, sourceId);
      setCredibilityData(res.credibility);
    } catch (err) {
      alert("Failed to load credibility details: " + err.message);
      setCredibilityModalSource(null);
    } finally {
      setCredibilityLoading(false);
    }
  };

  const handleOpenDiff = async (newId, oldId) => {
    if (!newId || !oldId) return;
    setDiffLoading(true);
    setShowDiffModal(true);
    try {
      const res = await fetchDiff(newId, oldId);
      setDiffData(res.diff);
    } catch (err) {
      alert("Failed to compute report diff: " + err.message);
      setShowDiffModal(false);
    } finally {
      setDiffLoading(false);
    }
  };

  // Feature 2: Annotations UI Renderer
  function renderAnnotationUI(targetType, targetId) {
    const matchingNotes = annotations.filter(
      (a) => a.target_type === targetType && a.target_id === String(targetId)
    );
    const isOpen =
      activeAnnotationTarget?.targetType === targetType &&
      activeAnnotationTarget?.targetId === String(targetId);

    const noteCount = matchingNotes.length;
    const unresolvedCount = matchingNotes.filter((a) => !a.resolved).length;

    return (
      <div style={{ marginTop: 6, display: "inline-block" }}>
        <button
          type="button"
          className={`annotation-trigger-btn${noteCount > 0 ? " has-notes" : ""}`}
          onClick={() => {
            if (isOpen) {
              setActiveAnnotationTarget(null);
            } else {
              setActiveAnnotationTarget({ targetType, targetId: String(targetId) });
              setNewAnnotationBody("");
            }
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {noteCount === 0 ? "Add note" : `${noteCount} note${noteCount > 1 ? "s" : ""}`}
          {unresolvedCount > 0 && (
            <span className="annotation-badge-unresolved">{unresolvedCount} open</span>
          )}
        </button>

        {isOpen && (
          <div className="annotation-container" style={{ marginTop: 8, maxWidth: 440 }}>
            <div className="annotation-header">
              <span>Personal Notes on this {targetType}</span>
              <button
                type="button"
                className="followup-close-btn"
                onClick={() => setActiveAnnotationTarget(null)}
              >
                ✕
              </button>
            </div>

            {/* List existing notes */}
            {matchingNotes.map((note) => (
              <div key={note.id} className={`annotation-item${note.resolved ? " resolved" : ""}`}>
                <div className="annotation-body">{note.body}</div>
                <div className="annotation-footer">
                  <span>{new Date(note.created_at).toLocaleDateString()}</span>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={note.resolved}
                        onChange={() => handleToggleResolveAnnotation(note.id, note.resolved)}
                      />
                      {note.resolved ? "Resolved" : "Mark resolved"}
                    </label>
                    <button
                      type="button"
                      style={{ background: "none", border: "none", color: "var(--rose)", cursor: "pointer", fontSize: 11 }}
                      onClick={() => handleDeleteAnnotation(note.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* New note input */}
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              <input
                type="text"
                className="followup-input"
                placeholder="Write a note to self…"
                value={newAnnotationBody}
                onChange={(e) => setNewAnnotationBody(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddAnnotation(targetType, targetId);
                }}
              />
              <button
                type="button"
                className="followup-submit-btn"
                disabled={annotationLoading || !newAnnotationBody.trim()}
                onClick={() => handleAddAnnotation(targetType, targetId)}
              >
                Save
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }



  // Stage animation timing adjusts based on depth and mode
  useEffect(() => {
    if (!loading) { setStageIdx(-1); return; }
    setStageIdx(0);
    const activeStages = compareMode ? CMP_STAGES : STAGES;
    const delay = depth === "quick" ? 1500 : depth === "deep" ? 3500 : 2500;
    const timers = activeStages.map((_, i) =>
      setTimeout(() => setStageIdx(i), i * delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading, depth, compareMode]);

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
    setPossibleDuplicateHint(null);
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
      if (compareMode) {
        if (!topicB.trim()) { setError("Topic B cannot be empty."); setLoading(false); return; }
        const data = await runComparativeResearch(topic.trim(), topicB.trim(), depth, filterSettings);
        setCompareReport(data.report);
        setReport(null);
        setMarkdown("");
      } else {
        const data = await runResearch(topic.trim(), depth, filterSettings, outputLanguage);
        setReport(data.report);
        setCompareReport(null);
        setMarkdown(data.markdown || "");
        if (data.possible_duplicate) {
          setPossibleDuplicateHint(data.possible_duplicate);
        }
      }
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

  function renderFollowUpUI(targetType, targetId) {
    const isFormActive =
      activeFollowUpTarget?.type === targetType &&
      activeFollowUpTarget?.id === String(targetId);

    const matchingResults = (report?.follow_ups || []).filter(
      (fu) => fu.target_type === targetType && fu.target_id === String(targetId)
    );

    return (
      <div className="followup-container" style={{ marginTop: 8 }}>
        {!isFormActive ? (
          <button
            className="followup-trigger-btn"
            onClick={() => {
              setActiveFollowUpTarget({ type: targetType, id: String(targetId) });
              setFollowUpQuestion("");
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{ marginRight: 4 }}>
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              <line x1="11" y1="8" x2="11" y2="14" />
              <line x1="8" y1="11" x2="14" y2="11" />
            </svg>
            Ask a follow-up
          </button>
        ) : (
          <div className="followup-form">
            <div className="followup-form-header">
              <span>Drill-down on this {targetType}</span>
              <button
                className="followup-close-btn"
                onClick={() => setActiveFollowUpTarget(null)}
              >
                ✕
              </button>
            </div>
            <div className="followup-chips">
              <button
                className="followup-chip"
                onClick={() => handleExecuteFollowUp(targetType, targetId, "Expand on this point with more details")}
              >
                Expand on this
              </button>
              <button
                className="followup-chip"
                onClick={() => handleExecuteFollowUp(targetType, targetId, "Find counter-arguments and opposing views")}
              >
                Find counter-arguments
              </button>
              <button
                className="followup-chip"
                onClick={() => handleExecuteFollowUp(targetType, targetId, "What is the source of disagreement here?")}
              >
                Source of disagreement?
              </button>
            </div>
            <div className="followup-input-row">
              <input
                type="text"
                className="followup-input"
                placeholder="Or type a custom follow-up question..."
                value={followUpQuestion}
                onChange={(e) => setFollowUpQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleExecuteFollowUp(targetType, targetId);
                }}
              />
              <button
                className="followup-submit-btn"
                disabled={followUpLoading || !followUpQuestion.trim()}
                onClick={() => handleExecuteFollowUp(targetType, targetId)}
              >
                {followUpLoading ? "Searching..." : "Ask"}
              </button>
            </div>
          </div>
        )}

        {/* Render nested follow-up results */}
        {matchingResults.map((fu) => (
          <div key={fu.follow_up_id} className={`followup-result-card ${fu.merged_into_parent ? "merged" : ""}`}>
            <div className="followup-result-header">
              <span className="followup-result-tag">Follow-up Answer</span>
              <span className="followup-result-q">"{fu.question}"</span>
            </div>
            <div className="followup-result-body">
              {renderInteractiveCitations(fu.summary)}
            </div>
            <div className="followup-result-actions">
              {!fu.merged_into_parent ? (
                <button
                  className="followup-action-btn merge"
                  onClick={() => handleMergeFollowUp(fu)}
                >
                  + Merge into report
                </button>
              ) : (
                <span className="followup-merged-badge">✓ Merged into report</span>
              )}
              <button
                className="followup-action-btn dismiss"
                onClick={() => handleDismissFollowUp(fu.follow_up_id)}
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    );
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

  // Interactive inline citation renderer for comparative report
  function renderCompareCitations(text, sources) {
    if (!text) return null;
    const parts = text.split(/(\[S\d+\])/g);
    return parts.map((part, i) => {
      if (/^\[S\d+\]$/.test(part)) {
        const sourceId = part.slice(1, -1);
        const sourceObj = sources?.find((s) => s.id === sourceId);
        return (
          <span key={i} className="inline-cite-container">
            <span className="inline-cite-hover">{part}</span>
            {sourceObj && (
              <div className="cite-popover">
                <div className="cite-popover-title">{sourceObj.title}</div>
                <div className="cite-popover-meta">
                  <span className="cite-popover-domain">{(() => { try { return new URL(sourceObj.url).hostname; } catch { return sourceObj.url; } })()}</span>
                  <span className={`tier-badge ${sourceObj.credibility_tier || "unrated"}`}>{sourceObj.credibility_tier || "Unrated"}</span>
                </div>
                {sourceObj.snippet && <div className="cite-popover-snippet">{sourceObj.snippet.slice(0, 180)}…</div>}
                <a href={sourceObj.url} target="_blank" rel="noopener noreferrer" className="cite-popover-link">Open source ↗</a>
              </div>
            )}
          </span>
        );
      }
      return part;
    });
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
        <div className="header-logo" style={{ display: "flex", alignItems: "center", gap: 10 }}>
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
          {/* Mode toggle */}
          <div className="mode-toggle">
            <button
              type="button"
              className={`mode-tab${!compareMode ? " active" : ""}`}
              onClick={() => { setCompareMode(false); setCompareReport(null); }}
            >
              Single Topic
            </button>
            <button
              type="button"
              className={`mode-tab${compareMode ? " active" : ""}`}
              onClick={() => { setCompareMode(true); setReport(null); setMarkdown(""); }}
            >
              Topic A vs B
            </button>
          </div>

          <div className="search-row">
            {compareMode ? (
              <>
                <textarea
                  className="search-textarea compare-half"
                  placeholder="Enter the first topic..."
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  rows={2}
                  maxLength={200}
                  disabled={loading}
                />
                <div className="compare-vs-divider">vs</div>
                <textarea
                  className="search-textarea compare-half"
                  placeholder="Enter the topic to compare..."
                  value={topicB}
                  onChange={(e) => setTopicB(e.target.value)}
                  rows={2}
                  maxLength={200}
                  disabled={loading}
                />
              </>
            ) : (
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
            )}
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

              {/* Language selector (Output Feature 3) */}
              <div style={{ width: 140 }}>
                <CustomSelectDropdown
                  value={outputLanguage}
                  onChange={setOutputLanguage}
                  options={LANGUAGE_OPTIONS}
                  disabled={loading}
                />
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
                <div className="progress-title">
                  {compareMode ? `Generating comparative report (${depth} mode)…` : `Generating research report (${depth} mode)…`}
                </div>
                <div className="progress-topic">
                  {compareMode ? `${topic} vs ${topicB}` : topic}
                </div>
              </div>
            </div>
            <div className="stages">
              {(compareMode ? CMP_STAGES : STAGES).map((stage, i) => {
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

        {/* Comparative Report */}
        {compareReport && !loading && (
          <div className="report-card">
            <div className="cmp-report-header">
              <div className="cmp-report-title">
                <span className="cmp-topic-a">{compareReport.topic_a}</span>
                <span className="cmp-vs-badge">vs</span>
                <span className="cmp-topic-b">{compareReport.topic_b}</span>
              </div>
              <div className="report-meta">
                {compareReport.sources?.length} sources · {compareReport.shared_dimensions?.length} dimensions · {compareReport.generated_at}
              </div>
            </div>

            <div className="cmp-table-wrapper">
              {/* Column headers */}
              <div className="cmp-table-head">
                <div className="cmp-col-dim">Dimension</div>
                <div className="cmp-col-pos">{compareReport.topic_a}</div>
                <div className="cmp-col-pos">{compareReport.topic_b}</div>
              </div>

              {compareReport.shared_dimensions?.map((dim, idx) => (
                <div key={idx} className="cmp-table-row">
                  <div className="cmp-col-dim">
                    <span className="cmp-dim-name">{dim.dimension_name}</span>
                    {dim.verdict_or_note && (
                      <div className="cmp-verdict">{dim.verdict_or_note}</div>
                    )}
                  </div>
                  <div className="cmp-col-pos cmp-pos-a">
                    <div className="cmp-pos-text">
                      {renderCompareCitations(dim.topic_a_position, compareReport.sources)}
                    </div>
                    <div className="cmp-source-badges">
                      {dim.topic_a_source_ids?.map((sid) => (
                        <span key={sid} className="source-badge">{sid}</span>
                      ))}
                    </div>
                  </div>
                  <div className="cmp-col-pos cmp-pos-b">
                    <div className="cmp-pos-text">
                      {renderCompareCitations(dim.topic_b_position, compareReport.sources)}
                    </div>
                    <div className="cmp-source-badges">
                      {dim.topic_b_source_ids?.map((sid) => (
                        <span key={sid} className="source-badge">{sid}</span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Sources list */}
            {compareReport.sources?.length > 0 && (
              <div style={{ padding: "16px 24px" }}>
                <div className="label">Sources</div>
                <div className="sources-list">
                  {compareReport.sources.map((src) => (
                    <div key={src.id} className="source-item">
                      <span className="source-id">{src.id}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="source-title">{src.title}</div>
                        <a className="source-url" href={src.url} target="_blank" rel="noopener noreferrer">{src.url}</a>
                      </div>
                      <span className={`tier-badge ${src.credibility_tier || "unrated"}`}>
                        {src.credibility_tier || "Unrated"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Report */}
        {report && !loading && (
          <div className="report-card">
            {/* Similar Report Hint Banner (Output Feature 2) */}
            {possibleDuplicateHint && (
              <div className="duplicate-hint-banner">
                <div className="duplicate-hint-content">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h1" />
                    <rect x="8" y="2" width="13" height="13" rx="2" />
                  </svg>
                  <div>
                    <strong>Similar Past Report Found:</strong> You previously researched <em>"{possibleDuplicateHint.topic}"</em> ({possibleDuplicateHint.generated_at}).
                  </div>
                </div>
                <div className="duplicate-hint-actions">
                  <button
                    type="button"
                    className="duplicate-diff-btn"
                    onClick={() => handleOpenDiff(
                      report.id || `report_${(report.topic || "topic").slice(0, 20).toLowerCase().replace(/\s+/g, "_")}`,
                      possibleDuplicateHint.report_id
                    )}
                  >
                    View What Changed ↗
                  </button>
                  <button
                    type="button"
                    className="duplicate-dismiss-btn"
                    onClick={() => setPossibleDuplicateHint(null)}
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}
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

                {report.output_language && report.output_language !== "en" && (
                  <span className="filter-summary-chip">
                    <span className="icon">🌐</span>
                    {(LANGUAGE_OPTIONS.find((l) => l.value === report.output_language)?.label || report.output_language).split(" ")[0]} Prose
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
                <button
                  className="action-btn"
                  onClick={() => handleOpenShare(report.id || currentReportId || `report_${(report.topic || "topic").slice(0, 20).toLowerCase().replace(/\s+/g, "_")}`)}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <circle cx="18" cy="5" r="3" />
                    <circle cx="6" cy="12" r="3" />
                    <circle cx="18" cy="19" r="3" />
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                  </svg>
                  Share
                </button>

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
                <button className={`action-btn${showBibPanel ? " active" : ""}`} onClick={handleToggleBibPanel}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  </svg>
                  Citations
                </button>
                <button className="action-btn" onClick={handleDownload}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                  Download
                </button>
              </div>
            </div>

            {/* Bibliography Panel (Output Feature 1) */}
            {showBibPanel && (
              <div className="bibliography-panel">
                <div className="bibliography-header">
                  <div className="bibliography-title">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                    </svg>
                    Export Bibliography & Citations
                  </div>
                  <div className="bib-style-selector">
                    {[
                      { id: "apa", label: "APA 7th" },
                      { id: "mla", label: "MLA 9th" },
                      { id: "chicago", label: "Chicago" },
                    ].map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        className={`bib-style-btn${bibStyle === s.id ? " active" : ""}`}
                        onClick={() => handleBibStyleChange(s.id)}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="followup-close-btn" onClick={() => setShowBibPanel(false)}>
                    ✕
                  </button>
                </div>

                {bibLoading ? (
                  <div className="bib-loading">Formatting citations…</div>
                ) : (
                  <>
                    <textarea
                      className="bib-textarea"
                      readOnly
                      value={bibText}
                      rows={Math.min(10, Math.max(4, (bibText || "").split("\n").length))}
                    />
                    <div className="bib-footer">
                      <span className="bib-hint">Auto-formatted in {bibStyle.toUpperCase()} style · Sorted alphabetically</span>
                      <button
                        type="button"
                        className={`action-btn${bibCopied ? " success" : ""}`}
                        onClick={handleCopyBib}
                      >
                        {bibCopied ? "✓ Copied to Clipboard" : "Copy Bibliography"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

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
                  {/* Session Delta Banner & Timeline */}
                  {session && session.what_changed_summary && (
                    <div className="session-delta-banner">
                      <div className="session-delta-title">
                        🔄 Multi-Pass Session Update ({session.passes?.length} passes)
                      </div>
                      <div className="session-delta-body">{session.what_changed_summary}</div>
                      <div className="session-timeline">
                        {session.passes?.map((p, pIdx) => (
                          <span key={pIdx} className="session-pass-badge">
                            Pass {pIdx + 1} ({p.depth}) · {p.run_at}
                            {p.additional_context && ` · "${p.additional_context}"`}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {report.confidence_note && (() => {
                    const noteText = report.confidence_note;
                    const isStaleness = noteText.includes("year old") || noteText.includes("dates are unavailable");
                    return (
                      <div className={isStaleness ? "confidence-banner" : "confidence-note"}>
                        <svg width={isStaleness ? 16 : 14} height={isStaleness ? 16 : 14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}>
                          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                          <line x1="12" y1="9" x2="12" y2="13" />
                          <line x1="12" y1="17" x2="12.01" y2="17" />
                        </svg>
                        <div>
                          {isStaleness && <div className="confidence-banner-label">Source Recency Warning</div>}
                          {noteText}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Key takeaways */}
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
                              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                                {renderFollowUpUI("takeaway", i)}
                                {renderAnnotationUI("takeaway", i)}
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
                          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
                            {renderFollowUpUI("section", sec.heading)}
                            {renderAnnotationUI("section", sec.heading)}
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
                          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
                            <button
                              type="button"
                              className="credibility-deepdive-btn"
                              onClick={() => handleOpenCredibility(src.id)}
                            >
                              🛡️ Trust Breakdown
                            </button>
                            {renderAnnotationUI("source", src.id)}
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

      {/* ── Slide-out History & Knowledge Base Search Drawer ── */}
      {showDrawer && (
        <div className="drawer-overlay" onClick={() => setShowDrawer(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title">Team Knowledge Base</div>
              <button className="close-btn" onClick={() => setShowDrawer(false)}>✕</button>
            </div>

            {/* FTS Search Input Bar */}
            <div className="drawer-search-box">
              <input
                type="text"
                className="drawer-search-input"
                placeholder="🔍 Search past research (full-text index)..."
                value={drawerQuery}
                onChange={(e) => setDrawerQuery(e.target.value)}
              />
            </div>

            <div className="history-list">
              {drawerSearchLoading && (
                <div style={{ fontSize: 12, color: "var(--text-3)", textAlign: "center", padding: 20 }}>
                  Searching FTS index…
                </div>
              )}

              {/* FTS Search Results Mode */}
              {drawerSearchResults !== null && !drawerSearchLoading && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", padding: "8px 16px" }}>
                    Search Results ({drawerSearchResults.length})
                  </div>
                  {drawerSearchResults.length === 0 ? (
                    <div style={{ fontSize: 13, color: "var(--text-3)", textAlign: "center", paddingTop: 20 }}>
                      No matching reports found for "{drawerQuery}".
                    </div>
                  ) : (
                    drawerSearchResults.map((res) => (
                      <div
                        key={res.report_id}
                        className="history-item"
                        style={{ marginBottom: 8, cursor: "pointer" }}
                        onClick={() => handleSelectHistoryReport(`${res.report_id}.md`)}
                      >
                        <div className="history-name">{res.topic}</div>
                        <div className="history-meta">{res.generated_at}</div>
                        {res.snippet && (
                          <div
                            className="search-snippet"
                            dangerouslySetInnerHTML={{ __html: res.snippet }}
                          />
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Normal Past Reports List Mode */}
              {drawerSearchResults === null && !drawerSearchLoading && (
                historyReports.length === 0 ? (
                  <div style={{ fontSize: 13, color: "var(--text-3)", textAlign: "center", paddingTop: 40 }}>
                    No saved reports found on server.
                  </div>
                ) : (
                  historyReports.map((item) => (
                    <div key={item.filename} className="history-item-row">
                      <div
                        className="history-item"
                        style={{ flex: 1 }}
                        onClick={() => handleSelectHistoryReport(item.filename)}
                      >
                        <div className="history-name" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          {item.filename}
                          {item.share_enabled && (
                            <span className="share-badge">Shared</span>
                          )}
                          {item.unresolved_annotations > 0 && (
                            <span className="annotation-badge-unresolved">
                              💬 {item.unresolved_annotations} open
                            </span>
                          )}
                        </div>
                        <div className="history-meta">
                          {(item.size_bytes / 1024).toFixed(1)} KB
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          className="history-continue-btn"
                          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid var(--border)" }}
                          onClick={() => handleOpenShare(item.report_id || item.filename.replace(/\.md$/, ""))}
                        >
                          🔗 Share
                        </button>
                        <button
                          className="history-continue-btn"
                          onClick={() => setContinueTarget(item)}
                        >
                          Continue
                        </button>
                      </div>
                    </div>
                  ))
                )
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Continuation Modal ── */}
      {continueTarget && (
        <div className="drawer-overlay" onClick={() => setContinueTarget(null)}>
          <div className="continue-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title">Continue Research Pass</div>
              <button className="close-btn" onClick={() => setContinueTarget(null)}>✕</button>
            </div>
            <div style={{ padding: "16px 20px" }}>
              <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 12 }}>
                Target report: <strong>{continueTarget.filename}</strong>
              </div>
              <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                Optional Refinement Context / Specific Focus
              </label>
              <textarea
                className="search-textarea"
                placeholder="e.g. 'Focus on new 2026 developments or pricing updates...'"
                value={additionalContextInput}
                onChange={(e) => setAdditionalContextInput(e.target.value)}
                rows={3}
                style={{ width: "100%", marginBottom: 16 }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button
                  className="action-btn"
                  onClick={() => setContinueTarget(null)}
                >
                  Cancel
                </button>
                <button
                  className="search-btn"
                  disabled={continueLoading}
                  onClick={handleExecuteContinue}
                >
                  {continueLoading ? "Running Pass..." : "Start Research Pass"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Share Report Modal ── */}
      {shareModalReportId && (
        <div className="drawer-overlay" onClick={() => setShareModalReportId(null)}>
          <div className="share-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title">Share Research Report</div>
              <button className="close-btn" onClick={() => setShareModalReportId(null)}>✕</button>
            </div>
            <div style={{ padding: "20px" }}>
              {shareLoading && !shareModalData ? (
                <div style={{ textAlign: "center", padding: 20 }}>
                  <div className="spinner" style={{ margin: "0 auto 12px" }} />
                  <div style={{ fontSize: 13, color: "var(--text-2)" }}>Loading share link…</div>
                </div>
              ) : (
                <>
                  <div className="share-toggle-row">
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)" }}>
                        {shareModalData?.share_enabled ? "Sharing is Enabled" : "Report is Private"}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
                        {shareModalData?.share_enabled
                          ? "Anyone with the unlisted link can view this read-only report."
                          : "Enable to generate a public/unlisted share URL."}
                      </div>
                    </div>
                    <button
                      className="search-btn"
                      style={{
                        padding: "6px 14px",
                        fontSize: 12,
                        background: shareModalData?.share_enabled ? "var(--rose)" : "var(--brand)",
                      }}
                      disabled={shareLoading}
                      onClick={handleToggleShare}
                    >
                      {shareModalData?.share_enabled ? "Revoke Link" : "Enable Link"}
                    </button>
                  </div>

                  {shareModalData?.share_enabled && (
                    <>
                      <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                        Public Unlisted Link
                      </label>
                      <div className="share-url-box">
                        <input
                          type="text"
                          readOnly
                          className="share-url-input"
                          value={shareModalData.share_url}
                        />
                        <button
                          className="action-btn"
                          style={{ padding: "4px 10px", fontSize: 11 }}
                          onClick={handleCopyShareUrl}
                        >
                          {shareCopied ? "✓ Copied" : "Copy Link"}
                        </button>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.4 }}>
                        🔒 <strong>Privacy note:</strong> Personal notes/annotations and follow-up history are NOT included on the public view.
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Report Diff Modal (Output Feature 2) ────────────────────────── */}
      {showDiffModal && (
        <div className="modal-backdrop" onClick={() => setShowDiffModal(false)}>
          <div className="modal-card diff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h1" />
                  <rect x="8" y="2" width="13" height="13" rx="2" />
                </svg>
                Report Comparison & Diff
              </div>
              <button type="button" className="followup-close-btn" onClick={() => setShowDiffModal(false)}>✕</button>
            </div>

            {diffLoading ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)", fontSize: 13 }}>
                Computing changes against prior report…
              </div>
            ) : diffData ? (
              <div className="diff-modal-body">
                <div className="diff-meta-bar">
                  <span><strong>Current:</strong> {diffData.new_topic}</span>
                  <span>vs</span>
                  <span><strong>Baseline:</strong> {diffData.old_topic}</span>
                  <span className="diff-sim-badge">Topic Match: {Math.round(diffData.topic_similarity * 100)}%</span>
                </div>

                {/* 1. Contradicted / Changed Findings (ROSE / RED - Most Prominent) */}
                {diffData.contradicted_takeaways?.length > 0 && (
                  <div className="diff-section contradicted">
                    <div className="diff-section-header rose">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      Potentially Contradicted or Shifted Findings ({diffData.contradicted_takeaways.length})
                    </div>
                    <div className="diff-items-list">
                      {diffData.contradicted_takeaways.map((item, idx) => (
                        <div key={idx} className="diff-item contradicted-card">
                          <div className="diff-item-text">{item.text}</div>
                          {item.note && <div className="diff-item-note">{item.note}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 2. New Takeaways */}
                {diffData.new_takeaways?.length > 0 && (
                  <div className="diff-section">
                    <div className="diff-section-header brand">
                      ✦ Newly Discovered Takeaways ({diffData.new_takeaways.length})
                    </div>
                    <div className="diff-items-list">
                      {diffData.new_takeaways.map((item, idx) => (
                        <div key={idx} className="diff-item new-card">
                          <div className="diff-item-text">{item.text}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. New Sources */}
                {diffData.new_sources?.length > 0 && (
                  <div className="diff-section">
                    <div className="diff-section-header emerald">
                      🌐 Newly Discovered Web Sources ({diffData.new_sources.length})
                    </div>
                    <div className="diff-sources-grid">
                      {diffData.new_sources.map((src) => (
                        <div key={src.id} className="diff-source-chip new">
                          <span className="source-title">{src.title}</span>
                          <a className="source-url" href={src.url} target="_blank" rel="noopener noreferrer">{src.url}</a>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. Stale / Unretrieved Sources */}
                {diffData.stale_sources?.length > 0 && (
                  <div className="diff-section">
                    <div className="diff-section-header muted">
                      💤 Sources from Baseline Not Retrieved in New Run ({diffData.stale_sources.length})
                    </div>
                    <div className="diff-sources-grid">
                      {diffData.stale_sources.map((src) => (
                        <div key={src.id} className="diff-source-chip stale">
                          <span className="source-title">{src.title}</span>
                          <span className="source-url">{src.url}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {diffData.new_takeaways?.length === 0 && diffData.contradicted_takeaways?.length === 0 && (
                  <div className="diff-empty-state">
                    Both reports yielded identical core takeaways and source coverage.
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* ── Source Credibility Deep-Dive Modal (Advanced Feature 1) ─────── */}
      {credibilityModalSource && (
        <div className="modal-backdrop" onClick={() => setCredibilityModalSource(null)}>
          <div className="modal-card credibility-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                Source Credibility & Trust Deep-Dive [{credibilityModalSource}]
              </div>
              <button type="button" className="followup-close-btn" onClick={() => setCredibilityModalSource(null)}>✕</button>
            </div>

            {credibilityLoading ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)", fontSize: 13 }}>
                Analyzing source trust score, tier heuristics, and bias indicators…
              </div>
            ) : credibilityData ? (
              <div className="credibility-modal-body">
                <div className="credibility-score-card">
                  <div className="credibility-gauge-wrapper">
                    <div className={`credibility-gauge-ring score-${Math.floor(credibilityData.trust_score / 20)}`}>
                      <span className="gauge-score-value">{credibilityData.trust_score}</span>
                      <span className="gauge-score-label">/ 100</span>
                    </div>
                  </div>
                  <div className="credibility-score-info">
                    <div className="credibility-score-title">
                      Trust & Authority Index
                    </div>
                    <div className="credibility-tier-row">
                      <span className={`tier-badge ${credibilityData.credibility_tier}`}>
                        {credibilityData.credibility_tier.toUpperCase()} TIER
                      </span>
                      <span className="domain-age-badge">{credibilityData.domain_age_hint}</span>
                    </div>
                    <div className="credibility-url">{credibilityData.url}</div>
                  </div>
                </div>

                <div className="credibility-detail-section">
                  <div className="credibility-section-label">Tier Evaluation Rationale</div>
                  <div className="credibility-text-box">{credibilityData.tier_reason}</div>
                </div>

                {credibilityData.bias_indicators?.length > 0 && (
                  <div className="credibility-detail-section">
                    <div className="credibility-section-label rose">⚠️ Risk & Bias Indicators</div>
                    <div className="bias-tags">
                      {credibilityData.bias_indicators.map((b, i) => (
                        <span key={i} className="bias-tag">{b}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}


