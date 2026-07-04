"""
src/output/output_formatter.py
───────────────────────────────
Converts a list of QuestionDict objects into a well-structured, PDF-ready
Markdown document and optionally writes it to disk.

Why Markdown as an intermediate format?
────────────────────────────────────────
Rather than writing directly to PDF from question data, we first render
Markdown for two reasons:

  1. Human-readability: The .md file is a useful deliverable on its own —
     it can be viewed in any text editor or GitHub/GitLab UI without tooling.

  2. Decoupled rendering: Markdown → HTML → PDF is a well-understood pipeline
     with mature tooling.  Changing the visual style only requires CSS edits,
     not changes to the Python formatting logic.

Markdown structure produced
────────────────────────────
  # Practice Questions
  *Source document:* ...
  *Generated on:* ...
  *Total questions:* N

  > Note: ...

  ---

  ## Question 1
  **<question text>**

  - **A)** <choice A>
  - **B)** <choice B>
  ...

  > ✅ **Correct Answer: C**

  **Explanation:**
  <explanation text>

  ---

  ## Question 2
  ...

Public API
──────────
    format_questions_to_markdown(questions, source_name, output_path) → str
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from observability.logger import get_logger

logger = get_logger(__name__)

QuestionDict = dict[str, Any]


# ─── Single-question renderer ──────────────────────────────────────────────────

def _render_question(q: QuestionDict, number: int) -> str:
    """
    Renders a single question dict as a Markdown section.

    Markdown design choices:
      • ## heading for each question gives clear visual separation and
        allows the PDF renderer to apply H2 styling (larger font, colour).
      • Bold (**...**) for the question text makes it immediately stand out.
      • Bullet list (- **A)**) for choices aligns with standard MCQ formatting
        and is correctly rendered by all Markdown processors.
      • Blockquote (>) for the correct answer creates a green-highlighted box
        in the PDF (via the CSS .correct-answer rule applied to blockquotes).
      • Plain paragraph + horizontal rule (---) for explanation and separator
        keeps the layout clean without nesting complexity.

    Args:
        q:      Validated QuestionDict from qa_generator.
        number: 1-based display number.

    Returns:
        Complete Markdown string for this question, including trailing separator.
    """
    lines: list[str] = []

    # Question heading — ## produces H2 in HTML, styled with the chapter colour
    lines.append(f"## Question {number}\n")

    # Question text in bold
    lines.append(f"**{q.get('question', '[No question text]')}**\n")

    # Choice list — iterate in fixed order A→D to guarantee consistent output
    choices: dict[str, str] = q.get("choices", {})
    for label in ("A", "B", "C", "D"):
        text = choices.get(label, "—")
        lines.append(f"- **{label})** {text}")

    lines.append("")  # blank line after the choice list

    # Correct answer in a Markdown blockquote (rendered as a coloured box in PDF)
    correct = q.get("correct_answer", "?")
    lines.append(f"> ✅ **Correct Answer: {correct}**")
    lines.append("")

    # Explanation — plain paragraph, no heading, to keep the layout compact
    explanation = q.get("explanation", "No explanation provided.")
    lines.append("**Explanation:**")
    lines.append("")
    lines.append(explanation)
    lines.append("")

    # Horizontal rule separates each question visually
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# ─── Document formatter ────────────────────────────────────────────────────────

def format_questions_to_markdown(
    questions: list[QuestionDict],
    source_name: str = "sample_document.pdf",
    output_path: Path | str | None = None,
) -> str:
    """
    Formats the full question set as a Markdown document.

    Document sections:
      1. Header — title, metadata (source, date, count)
      2. Disclaimer note — clarifies AI-generated content
      3. Horizontal rule separator
      4. One Markdown section per question (via _render_question)
      5. Footer — total count, generator attribution

    Args:
        questions:   List of validated QuestionDict objects.
        source_name: Name of the source PDF file, shown in the header.
        output_path: If provided, the Markdown is written to this path.
                     Parent directories are created if they do not exist.

    Returns:
        The complete Markdown string (also written to disk if output_path given).

    Raises:
        ValueError: If questions is empty — an empty document is not useful.
        OSError:    If the output file cannot be written.
    """
    if not questions:
        raise ValueError("Cannot format an empty question list.")

    # Use UTC timestamp for reproducibility — avoids timezone ambiguity
    # when the pipeline is run in different environments.
    now   = datetime.now(tz=timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    total = len(questions)

    # Derive a meaningful title from the source name
    title = _derive_title_from_source(source_name)

    # ── Header section ─────────────────────────────────────────────────────────
    header_lines = [
        f"# {title}",
        "",
        f"*Source document:* `{source_name}`",
        f"*Generated on:* {now}",
        f"*Total questions:* {total}",
        "",
        "> **Note:** All questions are original and generated exclusively from the "
        "source document above. They are intended for study and educational purposes only.",
        "",
        "---",
        "",
    ]

    # ── Question sections ──────────────────────────────────────────────────────
    # Each call to _render_question produces a self-contained Markdown block.
    question_sections: list[str] = [
        _render_question(q, i + 1) for i, q in enumerate(questions)
    ]

    # ── Footer section ─────────────────────────────────────────────────────────
    footer_lines = [
        "",
        "---",
        "",
        f"*End of {title} — {total} questions generated by AI Q&A Agent.*",
        "",
        "*Powered by PrakashPujariAI*",
    ]

    # Concatenate all parts into the final document
    full_markdown = (
        "\n".join(header_lines)
        + "\n".join(question_sections)
        + "\n".join(footer_lines)
    )

    # ── Persist to disk (optional) ─────────────────────────────────────────────
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_markdown, encoding="utf-8")
        logger.info(
            "Markdown saved: %s (%d questions, %d chars)",
            output_path.resolve(),
            total,
            len(full_markdown),
            extra={
                "output_path": str(output_path.resolve()),
                "question_count": total,
                "markdown_len":   len(full_markdown),
            },
        )

    return full_markdown


# ─── Text-only formatter ───────────────────────────────────────────────────────

def _get_youtube_title(video_id: str) -> str | None:
    """
    Fetch the actual YouTube video title using oEmbed API.

    This provides a meaningful name based on the video content rather than
    just the video ID. Falls back to None if the fetch fails.

    Args:
        video_id: The 11-character YouTube video ID.

    Returns:
        The video title, or None if fetch failed.
    """
    import urllib.request
    import json

    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Q&A Agent)"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("title", "").strip()
    except Exception:
        return None


def _extract_key_topics(text: str, max_topics: int = 5) -> list[str]:
    """
    Extract key topics from text content for meaningful naming.

    Uses simple keyword extraction based on capitalized words and common patterns
    to derive a meaningful title from the content itself.

    Args:
        text: The text content to analyze.
        max_topics: Maximum number of topics to extract.

    Returns:
        List of topic keywords/phrases.
    """
    import re

    # Keywords that indicate topic areas
    topic_keywords = [
        'AI', 'Machine Learning', 'Deep Learning', 'Neural Networks',
        'Cloud', 'Computing', 'Architecture', 'Design', 'Tools',
        'Software', 'Systems', 'Technology', 'Development', 'Programming',
        'Data', 'Analysis', 'Security', 'Networking', 'Storage',
        'Database', 'API', 'Application', 'Platform', 'Service',
        'Machine Learning', 'Artificial Intelligence', 'Computer Vision',
        'Natural Language', 'Text Processing', 'Document', 'Content',
    ]

    # Find keywords in text
    topics = []
    text_lower = text.lower()
    for keyword in topic_keywords:
        if keyword.lower() in text_lower:
            topics.append(keyword)

    # Also look for multi-word phrases with key terms
    phrase_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Tools?|Methods?|Approaches?|Strategies?|Systems?|Design|Computing|Architecture)))'
    phrase_matches = re.findall(phrase_pattern, text[:2000])
    for phrase in phrase_matches:
        phrase_lower = phrase.lower()
        # Avoid duplicates
        if phrase_lower not in [t.lower() for t in topics]:
            topics.append(phrase)

    # Remove duplicates while preserving order
    seen = set()
    unique_topics = []
    for t in topics:
        t_lower = t.lower()
        if t_lower not in seen and len(t) > 3:
            seen.add(t_lower)
            unique_topics.append(t)

    return unique_topics[:max_topics]


def _derive_title_from_summary(summary_text: str) -> str:
    """
    Derive a meaningful document title from the generated summary content.

    This is used when the source title (e.g., YouTube video title) is unavailable
    or generic. It analyzes the summary to find key topics and creates a name
    that reflects the actual content.

    Args:
        summary_text: The generated summary text.

    Returns:
        A meaningful title based on the content.
    """
    # Extract key topics from the summary
    topics = _extract_key_topics(summary_text)

    if topics:
        # Use the first most relevant topic
        topic = topics[0]
        # Clean up the topic for display
        topic = topic.replace("_", " ").replace("-", " ")
        topic = topic.title()
        return f"{topic} Analysis"

    # Fallback to generic but clean name
    return "Document Analysis"


def _get_youtube_title(video_id: str) -> str | None:
    """
    Fetch the actual YouTube video title using oEmbed API.

    This provides a meaningful name based on the video content rather than
    just the video ID. Falls back to None if the fetch fails.

    Args:
        video_id: The 11-character YouTube video ID.

    Returns:
        The video title, or None if fetch failed.
    """
    import urllib.request
    import json

    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Q&A Agent)"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("title", "").strip()
    except Exception:
        return None


def _derive_title_from_source(source_name: str) -> str:
    """
    Derive a meaningful document title from the source filename or URL.

    Examples:
        "sample_document.pdf" → "Sample Document Analysis"
        "cloud_computing.pdf" → "Cloud Computing Analysis"
        "https://example.com/doc" → "Document Analysis"
        "https://youtu.be/dQw4w9WgXcQ" → "Actual Video Title Analysis"
    """
    # Handle YouTube URLs specially - try to fetch actual title
    if "youtube.com" in source_name or "youtu.be" in source_name:
        import re as _re
        video_id_match = _re.search(
            r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
            source_name
        )
        if video_id_match:
            video_id = video_id_match.group(1)
            title = _get_youtube_title(video_id)
            if title:
                # Sanitize the title for display
                title = title.replace("_", " ").replace("-", " ")
                title = title.title()
                return f"{title} Analysis"
        # Fallback to generic but clean name for unavailable videos
        return "YouTube Video Analysis"

    # Remove path and extension
    name = Path(source_name).stem

    # Replace underscores and hyphens with spaces
    name = name.replace("_", " ").replace("-", " ")

    # Title case the name
    name = name.title()

    # If name is empty or just "document", use generic title
    if not name or name.lower() in ("document", "source"):
        return "Document Analysis"

    return f"{name} Analysis"


def _derive_filename_from_source(source_name: str) -> str:
    """
    Derive a meaningful PDF filename from the source name.

    Unlike the title, this produces a filename-safe string without spaces
    or special characters. Used for output PDF naming.

    Examples:
        "cloud_computing.pdf" → "Cloud_Computing_Analysis.pdf"
        "sample_document.pdf" → "Sample_Document_Analysis.pdf"
        "https://example.com/doc" → "Document_Analysis.pdf"
        "https://youtu.be/dQw4w9WgXcQ" → "Actual_Video_Title.pdf"
    """
    # Handle YouTube URLs specially - try to fetch actual title
    if "youtube.com" in source_name or "youtu.be" in source_name:
        import re as _re
        video_id_match = _re.search(
            r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
            source_name
        )
        if video_id_match:
            video_id = video_id_match.group(1)
            title = _get_youtube_title(video_id)
            if title:
                # Sanitize for filename
                safe_name = title.replace(" ", "_").replace(":", "").replace("/", "_")
                safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-", "."))
                if safe_name:
                    return f"{safe_name}.pdf"
        # Fallback to video ID-based name (clean format)
        if video_id_match:
            return f"YouTube_{video_id_match.group(1)}.pdf"
        return "YouTube_Video.pdf"

    title = _derive_title_from_source(source_name)
    # Convert to filename-safe: replace spaces with underscores, remove special chars
    safe_name = title.replace(" ", "_").replace(":", "").replace("/", "_")
    # Remove any characters that aren't alphanumeric, underscore, hyphen, or dot
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-", "."))
    # Ensure .pdf extension
    if not safe_name.endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    return safe_name


def _derive_filename_from_summary(summary_text: str) -> str:
    """
    Derive a meaningful PDF filename from the generated summary content.

    This is the key function for creating content-based filenames. It analyzes
    the summary to extract key topics and creates a filename that reflects
    the actual content.

    Args:
        summary_text: The generated summary text.

    Returns:
        A filename-safe string based on the content topics.
    """
    title = _derive_title_from_summary(summary_text)
    safe_name = title.replace(" ", "_").replace(":", "").replace("/", "_")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-", "."))
    if not safe_name.endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    return safe_name


def format_text_to_markdown(
    text: str,
    source_name: str = "document",
    output_path: Path | str | None = None,
) -> str:
    """Format an LLM-produced text summary as a standalone Markdown document."""
    now = datetime.now(tz=timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # Derive a meaningful title from the source name
    title = _derive_title_from_source(source_name)

    lines = [
        f"# {title}",
        "",
        f"*Source:* `{source_name}`",
        f"*Captured on:* {now}",
        "",
        "---",
        "",
        text,
        "",
        "---",
        "",
        f"*End of {title} — generated by AI Q&A Agent.*",
        "",
        "*Powered by PrakashPujariAI*",
    ]

    full_markdown = "\n".join(lines)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_markdown, encoding="utf-8")
        logger.info(
            "Text markdown saved: %s (%d chars)",
            output_path.resolve(),
            len(full_markdown),
            extra={"output_path": str(output_path.resolve()), "markdown_len": len(full_markdown)},
        )

    return full_markdown


# ─── Combined formatter (text + questions) ────────────────────────────────────

def format_combined_to_markdown(
    text: str,
    questions: list[QuestionDict],
    source_name: str = "document",
    output_path: Path | str | None = None,
) -> str:
    """
    Format an LLM text summary followed by MCQ questions as one Markdown document.

    When the source title is generic (e.g., "YouTube Video Analysis" for unavailable videos),
    this function derives a content-based title from the generated summary text to provide
    a more meaningful document name.

    Returns:
        The complete Markdown string (also written to disk if output_path given).
    """
    if not questions:
        raise ValueError("Cannot format an empty question list.")

    now   = datetime.now(tz=timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    total = len(questions)

    # Derive a meaningful title from the source name
    title = _derive_title_from_source(source_name)

    # If title is generic (YouTube video unavailable), derive from content
    if title == "YouTube Video Analysis":
        title = _derive_title_from_summary(text)

    header_lines = [
        f"# {title} & Practice Questions",
        "",
        f"*Source:* `{source_name}`",
        f"*Generated on:* {now}",
        f"*Total questions:* {total}",
        "",
        "---",
        "",
        f"# Part 1 — {title} Summary",
        "",
        text,
        "",
        "---",
        "",
        "# Part 2 — Practice Questions",
        "",
        "> **Note:** All questions are original and generated exclusively from the source document above.",
        "",
        "---",
        "",
    ]

    question_sections: list[str] = [
        _render_question(q, i + 1) for i, q in enumerate(questions)
    ]

    footer_lines = [
        "",
        "---",
        "",
        f"*End of {title} — {total} questions generated by AI Q&A Agent.*",
        "",
        "*Powered by PrakashPujariAI*",
    ]

    full_markdown = (
        "\n".join(header_lines)
        + "\n".join(question_sections)
        + "\n".join(footer_lines)
    )

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_markdown, encoding="utf-8")
        logger.info(
            "Combined markdown saved: %s (%d questions, %d chars)",
            output_path.resolve(),
            total,
            len(full_markdown),
            extra={
                "output_path":    str(output_path.resolve()),
                "question_count": total,
                "markdown_len":   len(full_markdown),
            },
        )

    return full_markdown
