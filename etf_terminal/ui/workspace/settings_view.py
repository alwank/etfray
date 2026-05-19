"""Settings view for configuring app behavior."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Input, Button, Label
from textual.widget import Widget

from etf_terminal.db.database import load_settings, save_settings, Settings


class SettingsView(VerticalScroll):
    DEFAULT_CSS = """
    SettingsView {
        padding: 1 2;
    }
    SettingsView Input {
        width: 40;
        margin-bottom: 1;
    }
    SettingsView Button {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        s = load_settings()

        yield Static("[bold]Settings[/bold]\n")

        yield Static("── EDGAR ──")
        yield Label("EDGAR Identity (email):")
        yield Input(value=s.edgar_identity, id="edgar-identity", placeholder="your.name@email.com")

        yield Static("\n── IBKR Connection ──")
        yield Label("Host:")
        yield Input(value=s.ibkr_host, id="ibkr-host")
        yield Label("Port:")
        yield Input(value=str(s.ibkr_port), id="ibkr-port")
        yield Label("Client ID:")
        yield Input(value=str(s.ibkr_client_id), id="ibkr-client-id")

        yield Static("\n── Thresholds ──")
        yield Label("Margin Warning (cushion):")
        yield Input(value=str(s.margin_warning_cushion), id="margin-warning")
        yield Label("Leverage Warning:")
        yield Input(value=str(s.leverage_warning), id="leverage-warning")

        yield Static("\n── Paths ──")
        yield Label("Export Directory:")
        yield Input(value=s.export_dir, id="export-dir")

        yield Button("Save Settings", id="save-settings", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            s = Settings(
                edgar_identity=self.query_one("#edgar-identity", Input).value,
                ibkr_host=self.query_one("#ibkr-host", Input).value,
                ibkr_port=int(self.query_one("#ibkr-port", Input).value or "7497"),
                ibkr_client_id=int(self.query_one("#ibkr-client-id", Input).value or "1"),
                margin_warning_cushion=float(self.query_one("#margin-warning", Input).value or "0.15"),
                leverage_warning=float(self.query_one("#leverage-warning", Input).value or "2.0"),
                export_dir=self.query_one("#export-dir", Input).value,
            )
            save_settings(s)
            self.notify("Settings saved.")
