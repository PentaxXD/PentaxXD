import json
from typing import Optional

import typer

from .items import parse_line_items
from .extractor import extract_text_from_pdf


app = typer.Typer(add_completion=False)


@app.command()
def items(
    pdf: str = typer.Argument(..., help="Path to PDF"),
    page: Optional[int] = typer.Option(None, "--page", help="1-based page to parse"),
    json_only: bool = typer.Option(False, "--json-only", help="Only output items JSON"),
):
    text = extract_text_from_pdf(pdf, pages=[page] if page else None)
    parsed = [it.to_dict() for it in parse_line_items(text)]
    payload = json.dumps(parsed, ensure_ascii=False, indent=2)
    typer.echo(payload)
