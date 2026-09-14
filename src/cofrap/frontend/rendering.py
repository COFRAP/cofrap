from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

PRESENTATION_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=PRESENTATION_ROOT / "templates")


def fragment(request: Request, name: str, **context):
    return templates.TemplateResponse(
        request=request, name=f"fragments/{name}.html", context=context
    )


def page(request: Request, name: str, **context):
    return templates.TemplateResponse(
        request=request, name="page.html", context={"fragment_name": name, **context}
    )
