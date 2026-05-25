"""Modal prompt when a newer etfray release is available on PyPI."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

PYPI_URL = "https://pypi.org/project/etfray/"


class VersionUpdateModal(ModalScreen[str]):
    """Ask user to upgrade or skip until the next release."""

    DEFAULT_CSS = """
    VersionUpdateModal {
        align: center middle;
    }
    #version-update-dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    #version-update-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #version-update-body {
        margin-bottom: 1;
    }
    #version-update-actions {
        height: auto;
        align: center middle;
    }
    #version-update-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, installed: str, latest: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._installed = installed
        self._latest = latest

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="version-update-dialog"):
                yield Static("Update available", id="version-update-title")
                yield Static(self._body_text(), id="version-update-body")
                with Center():
                    with Vertical(id="version-update-actions"):
                        yield Button("Update Now", id="btn-update", variant="primary")
                        yield Button("Skip until next version", id="btn-skip")

    def _body_text(self) -> str:
        return (
            f"Installed: {self._installed}\n"
            f"Latest:    {self._latest}\n\n"
            f"[dim]{PYPI_URL}[/dim]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-update":
            self.dismiss("update")
        elif event.button.id == "btn-skip":
            self.dismiss("skip")
