export async function checkHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function runResearch(topic, depth = "standard") {
  const res = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, depth }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Research request failed");
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
