import re
import logging
from typing import List, Set, Tuple, Optional
from src.models.schemas import Source, ReportSection, Citation, KeyTakeaway

logger = logging.getLogger(__name__)


class CitationMapper:
    def validate_and_map_citations(
        self,
        sections: List[ReportSection],
        valid_sources: List[Source],
        takeaways: Optional[List[KeyTakeaway]] = None,
    ) -> Tuple[List[ReportSection], List[KeyTakeaway], List[str]]:
        """
        Parses [S#] markers in section prose content, validates against valid_sources,
        creates Citation models, flags ungrounded sections, and computes takeaway corroboration counts.
        Returns (updated_sections, updated_takeaways, list_of_grounding_warnings).
        """
        valid_source_ids: Set[str] = {s.id for s in valid_sources}
        source_map = {s.id: s for s in valid_sources}

        updated_sections: List[ReportSection] = []
        warnings: List[str] = []

        # Regex pattern matching [S1], [S12], etc.
        citation_pattern = re.compile(r"\[(S\d+)\]")

        for sec in sections:
            found_markers = citation_pattern.findall(sec.content)
            unique_markers = list(dict.fromkeys(found_markers))

            citations: List[Citation] = []
            invalid_markers: List[str] = []

            for marker in unique_markers:
                if marker in valid_source_ids:
                    source_obj = source_map[marker]
                    citations.append(
                        Citation(
                            source_id=marker,
                            quote_or_paraphrase=f"{source_obj.title} ({source_obj.url})",
                        )
                    )
                else:
                    invalid_markers.append(marker)

            # Strip invalid/hallucinated citation markers from content
            cleaned_content = sec.content
            for invalid_m in invalid_markers:
                cleaned_content = cleaned_content.replace(f"[{invalid_m}]", "")
                warnings.append(
                    f"Removed hallucinated citation [{invalid_m}] from section '{sec.heading}'."
                )

            # Clean up double spaces created by marker removals
            cleaned_content = re.sub(r"\s+", " ", cleaned_content).strip()

            if not citations:
                warn_msg = f"Section '{sec.heading}' contains zero valid citations — potential grounding issue."
                warnings.append(warn_msg)
                logger.warning(warn_msg)

            updated_sec = sec.model_copy(
                update={"content": cleaned_content, "citations": citations}
            )
            updated_sections.append(updated_sec)

        updated_takeaways: List[KeyTakeaway] = []
        if takeaways:
            for kt in takeaways:
                valid_sids = [sid for sid in kt.source_ids if sid in valid_source_ids]
                distinct_count = len(set(valid_sids))
                updated_kt = kt.model_copy(
                    update={
                        "source_ids": valid_sids,
                        "corroboration_count": max(1, distinct_count) if valid_sids else 1,
                    }
                )
                updated_takeaways.append(updated_kt)

        return updated_sections, updated_takeaways, warnings

    @staticmethod
    def audit_recency_and_confidence(
        sources: List[Source], existing_note: Optional[str] = None
    ) -> Optional[str]:
        """
        Audits publication dates of sources for staleness (> 12 months median age) or missing dates.
        Appends recency warnings to the existing confidence_note.
        """
        from datetime import datetime, date

        if not sources:
            return existing_note

        notes = [existing_note] if existing_note else []

        today = date.today()
        ages_in_days = []
        missing_date_count = 0

        for s in sources:
            p_date_str = s.published_date
            if not p_date_str or not str(p_date_str).strip():
                missing_date_count += 1
                continue

            p_str = str(p_date_str).strip()
            parsed_date = None

            # Try parsing YYYY-MM-DD or ISO timestamp
            if len(p_str) >= 10:
                try:
                    parsed_date = datetime.strptime(p_str[:10], "%Y-%m-%d").date()
                except ValueError:
                    pass
            elif len(p_str) == 4 and p_str.isdigit():
                try:
                    parsed_date = date(int(p_str), 1, 1)
                except ValueError:
                    pass

            if parsed_date:
                age = (today - parsed_date).days
                if age >= 0:
                    ages_in_days.append(age)
            else:
                missing_date_count += 1

        total_sources = len(sources)
        if total_sources > 0 and (missing_date_count / total_sources) > 0.5:
            notes.append("Publish dates are unavailable for most sources in this report.")

        if ages_in_days:
            ages_in_days.sort()
            mid = len(ages_in_days) // 2
            if len(ages_in_days) % 2 != 0:
                median_age = ages_in_days[mid]
            else:
                median_age = (ages_in_days[mid - 1] + ages_in_days[mid]) / 2

            if median_age > 365:
                notes.append("Most sources in this report are over a year old — consider re-running with a narrower date range if recent developments matter for this topic.")

        return " ".join(notes) if notes else None


