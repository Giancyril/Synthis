import re
import logging
from typing import List, Set, Tuple
from src.models.schemas import Source, ReportSection, Citation

logger = logging.getLogger(__name__)


class CitationMapper:
    def validate_and_map_citations(
        self, sections: List[ReportSection], valid_sources: List[Source]
    ) -> Tuple[List[ReportSection], List[str]]:
        """
        Parses [S#] markers in section prose content, validates against valid_sources,
        creates Citation models, and flags ungrounded sections.
        Returns (updated_sections, list_of_grounding_warnings).
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

        return updated_sections, warnings
