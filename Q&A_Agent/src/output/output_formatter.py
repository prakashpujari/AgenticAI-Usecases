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

# Type alias matching the schema in generation/qa_generator.py
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

    # ── Header section ─────────────────────────────────────────────────────────
    header_lines = [
        "# Practice Questions",
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
        f"*End of Practice Questions — {total} questions generated by AI Q&A Agent.*",
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
