export async function checkHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function runResearch(topic, depth = "standard", filterSettings = {}) {
  const payload = {
    topic,
    depth,
    date_filter: filterSettings.date_filter || "any",
    custom_start_date: filterSettings.custom_start_date || null,
    custom_end_date: filterSettings.custom_end_date || null,
    domain_mode: filterSettings.domain_mode || "none",
    domain_list: filterSettings.domain_list || [],
    source_category: filterSettings.source_category || "general",
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
