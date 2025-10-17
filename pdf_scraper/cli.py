import json
from pathlib import Path
from typing import List, Optional

import typer

from .extractor import extract_text_from_pdf
from .filtering import filter_lines
from .fields import extract_fields
from .config import load_config, ScrapeConfig
from .items import parse_line_items, parse_line_items_layout_aware


app = typer.Typer(add_completion=False, no_args_is_help=True)


def _read_text(pdf: str, pages: Optional[List[int]]) -> str:
    return extract_text_from_pdf(pdf, pages=pages)


@app.command()
def extract(
    pdf: str = typer.Argument(..., help="Path to PDF file"),
    page: List[int] = typer.Option(None, "--page", help="1-based page number; can be repeated"),
):
    """Extract raw text from PDF and print to stdout."""
    text = _read_text(pdf, page)
    typer.echo(text)


@app.command()
def filter(
    pdf: str = typer.Argument(..., help="Path to PDF file"),
    include: List[str] = typer.Option(None, "--include", help="Include regex; can be repeated"),
    exclude: List[str] = typer.Option(None, "--exclude", help="Exclude regex; can be repeated"),
    context: int = typer.Option(0, "--context", help="Context lines around include matches"),
    ignore_case: bool = typer.Option(True, "--ignore-case/--case-sensitive"),
    page: List[int] = typer.Option(None, "--page", help="1-based page number; can be repeated"),
):
    """Extract text and filter by include/exclude patterns."""
    text = _read_text(pdf, page)
    filtered = filter_lines(
        text,
        include_patterns=include,
        exclude_patterns=exclude,
        context_lines=context,
        ignore_case=ignore_case,
    )
    typer.echo(filtered)


@app.command()
def fields(
    pdf: str = typer.Argument(..., help="Path to PDF file"),
    config: Optional[str] = typer.Option(None, "--config", help="YAML/JSON config file with fields"),
    page: List[int] = typer.Option(None, "--page", help="1-based page number; can be repeated"),
    output: Optional[str] = typer.Option(None, "--out", help="Where to write JSON results"),
):
    """Extract fields defined in a config (YAML/JSON)."""
    if not config:
        typer.echo("--config is required for fields extraction", err=True)
        raise typer.Exit(code=2)

    cfg = load_config(config)
    text = _read_text(pdf, page or cfg.pages)
    results = extract_fields(text, cfg.fields)

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    typer.echo(payload)


@app.command()
def scrape(
    pdf: str = typer.Argument(..., help="Path to PDF file"),
    config: Optional[str] = typer.Option(None, "--config", help="YAML/JSON config to control scraping"),
    include: List[str] = typer.Option(None, "--include", help="Include regex; can be repeated"),
    exclude: List[str] = typer.Option(None, "--exclude", help="Exclude regex; can be repeated"),
    context: int = typer.Option(None, "--context", help="Context lines around include matches"),
    ignore_case: bool = typer.Option(True, "--ignore-case/--case-sensitive"),
    output: Optional[str] = typer.Option(None, "--out", help="Where to write JSON results"),
    page: List[int] = typer.Option(None, "--page", help="1-based page number; can be repeated"),
):
    """End-to-end scrape: extract text, filter lines, extract fields."""
    cfg = ScrapeConfig()
    if config:
        cfg = load_config(config)

    effective_pages = page or cfg.pages
    text = _read_text(pdf, effective_pages)

    effective_include = include if include is not None else cfg.include_patterns
    effective_exclude = exclude if exclude is not None else cfg.exclude_patterns
    effective_context = context if context is not None else cfg.context_lines

    filtered_text = filter_lines(
        text,
        include_patterns=effective_include,
        exclude_patterns=effective_exclude,
        context_lines=effective_context,
        ignore_case=ignore_case,
    )

    results = extract_fields(filtered_text, cfg.fields)
    payload = json.dumps({
        "text": filtered_text,
        "fields": results,
    }, ensure_ascii=False, indent=2)

    final_output_path = output or cfg.output_path
    if final_output_path:
        Path(final_output_path).write_text(payload, encoding="utf-8")

    typer.echo(payload)


@app.command()
def items(
    pdf: str = typer.Argument(..., help="Path to PDF file"),
    page: Optional[int] = typer.Option(None, "--page", help="1-based page number to parse"),
    out: Optional[str] = typer.Option(None, "--out", help="Write results to path; .csv => CSV, otherwise JSON"),
):
    """Parse invoice line items into structured rows (JSON or CSV)."""
    # Prefer layout-aware parsing for accurate column grouping
    rows = [li.to_dict() for li in parse_line_items_layout_aware(pdf, page=page or 1)]

    if out:
        ext = Path(out).suffix.lower()
        if ext == ".csv":
            import csv
            fieldnames = (
                list(rows[0].keys())
                if rows
                else [
                    "order_qty",
                    "ship_qty",
                    "units",
                    "item",
                    "upc",
                    "brand",
                    "description",
                    "pack_size",
                    "price",
                    "extended_price",
                ]
            )
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        else:
            payload = json.dumps(rows, ensure_ascii=False, indent=2)
            Path(out).write_text(payload, encoding="utf-8")
        return

    # Default: print JSON to stdout
    typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
