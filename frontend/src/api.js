export async function checkHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function runResearch(topic, depth = "standard", filterSettings = {}, outputLanguage = "en") {
  const payload = {
    topic,
    depth,
    date_filter: filterSettings.date_filter || "any",
    custom_start_date: filterSettings.custom_start_date || null,
    custom_end_date: filterSettings.custom_end_date || null,
    domain_mode: filterSettings.domain_mode || "none",
    domain_list: filterSettings.domain_list || [],
    source_category: filterSettings.source_category || "general",
    output_language: outputLanguage || "en",
  };

  const res = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : err.detail || "Research request failed";
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchReports() {
  const res = await fetch("/api/reports");
  if (!res.ok) throw new Error("Failed to fetch past reports");
  return res.json();
}

export async function fetchReportByFilename(filename) {
  const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`);
  if (!res.ok) throw new Error("Failed to fetch report detail");
  return res.json();
}

export async function executeFollowUpQuery(report, targetType, targetId, question) {
  const res = await fetch("/api/research/follow-up", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      report,
      target_type: targetType,
      target_id: String(targetId),
      question,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Follow-up query failed.");
  }
  return res.json();
}

export async function runComparativeResearch(topicA, topicB, depth = "standard", filterSettings = {}) {
  const payload = {
    topic_a: topicA,
    topic_b: topicB,
    depth,
    date_filter: filterSettings.date_filter || "any",
    custom_start_date: filterSettings.custom_start_date || null,
    custom_end_date: filterSettings.custom_end_date || null,
    domain_mode: filterSettings.domain_mode || "none",
    domain_list: filterSettings.domain_list || [],
    source_category: filterSettings.source_category || "general",
  };

  const res = await fetch("/api/research/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Comparative research failed.");
  }
  return res.json();
}

export async function continueResearchSession(filename, report, additionalContext, depth = "standard") {
  const res = await fetch("/api/research/continue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename,
      report,
      additional_context: additionalContext || null,
      depth,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Session continuation failed.");
  }
  return res.json();
}


// ── Sharing (Feature 1) ──────────────────────────────────────────────────────

export async function shareReport(reportId) {
  const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/share`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to enable sharing.");
  }
  return res.json();
}

export async function unshareReport(reportId) {
  const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/share`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to revoke sharing.");
  }
  return res.json();
}

export async function fetchPublicReport(shareToken) {
  const res = await fetch(`/api/public/reports/${encodeURIComponent(shareToken)}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error("Report not found or sharing has been disabled.");
    throw new Error("Failed to load shared report.");
  }
  return res.json();
}

// ── Annotations (Feature 2) ──────────────────────────────────────────────────

export async function fetchAnnotations(reportId) {
  const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/annotations`);
  if (!res.ok) throw new Error("Failed to fetch annotations.");
  return res.json();
}

export async function createAnnotation(reportId, targetType, targetId, body, author) {
  const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_type: targetType, target_id: String(targetId), body, author: author || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create annotation.");
  }
  return res.json();
}

export async function patchAnnotation(annotationId, patch) {
  const res = await fetch(`/api/annotations/${encodeURIComponent(annotationId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update annotation.");
  }
  return res.json();
}

export async function deleteAnnotation(annotationId) {
  const res = await fetch(`/api/annotations/${encodeURIComponent(annotationId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete annotation.");
  }
}

// ── Search (Feature 3) ───────────────────────────────────────────────────────

export async function searchReports(query) {
  const res = await fetch(`/api/reports/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error("Search failed.");
  return res.json();
}

// ── Bibliography Export (Output Feature 1) ───────────────────────────────────

export async function fetchBibliography(reportId, style = "apa") {
  const res = await fetch(
    `/api/reports/${encodeURIComponent(reportId)}/bibliography?style=${encodeURIComponent(style)}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch bibliography.");
  }
  return res.json();
}

// ── Report Diffing (Output Feature 2) ────────────────────────────────────────

export async function fetchDiff(reportId, againstReportId) {
  const res = await fetch(
    `/api/reports/${encodeURIComponent(reportId)}/diff?against=${encodeURIComponent(againstReportId)}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to compute report diff.");
  }
  return res.json(); // { status, diff }
}

// ── Source Credibility (Advanced Feature 1) ───────────────────────────────────

export async function fetchSourceCredibility(reportId, sourceId) {
  const res = await fetch(
    `/api/reports/${encodeURIComponent(reportId)}/sources/${encodeURIComponent(sourceId)}/credibility`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch source credibility.");
  }
  return res.json();
}

// ── Outline Generator (Advanced Feature 3) ────────────────────────────────────

export async function fetchResearchOutline(topic, depth = "standard") {
  const res = await fetch("/api/research/outline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, depth }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to generate research outline.");
  }
  return res.json(); // { status, outline }
}



