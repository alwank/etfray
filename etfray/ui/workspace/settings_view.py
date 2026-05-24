"""Settings view for configuring app behavior."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Label, Static

from etfray.db.database import Settings, load_settings, save_settings


class SettingsView(VerticalScroll):
    DEFAULT_CSS = """
    SettingsView {
        height: 1fr;
        min-height: 1fr;
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
        yield Label("Freshness - Days Fresh:")
        yield Input(value=str(s.freshness_days_fresh), id="freshness-fresh")
        yield Label("Freshness - Days Acceptable:")
        yield Input(value=str(s.freshness_days_acceptable), id="freshness-acceptable")
        yield Label("Margin Warning (cushion):")
        yield Input(value=str(s.margin_warning_cushion), id="margin-warning")
        yield Label("Leverage Warning:")
        yield Input(value=str(s.leverage_warning), id="leverage-warning")

        yield Static("\n── Data ──")
        yield Label("Data Source (auto / edgar / web):")
        yield Input(value=s.data_source, id="data-source")
        yield Label("Cache Directory:")
        yield Input(value=s.cache_dir, id="cache-dir")

        yield Static("\n── Paths ──")
        yield Label("Export Directory:")
        yield Input(value=s.export_dir, id="export-dir")

        yield Button("Save Settings", id="save-settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            data_source = self.query_one("#data-source", Input).value or "auto"
            if data_source not in {"auto", "edgar", "web"}:
                self.notify("data_source must be 'auto', 'edgar', or 'web'", severity="error")
                return
            s = Settings(
                edgar_identity=self.query_one("#edgar-identity", Input).value,
                ibkr_host=self.query_one("#ibkr-host", Input).value,
                ibkr_port=int(self.query_one("#ibkr-port", Input).value or "7497"),
                ibkr_client_id=int(self.query_one("#ibkr-client-id", Input).value or "1"),
                freshness_days_fresh=int(self.query_one("#freshness-fresh", Input).value or "30"),
                freshness_days_acceptable=int(self.query_one("#freshness-acceptable", Input).value or "90"),
                margin_warning_cushion=float(self.query_one("#margin-warning", Input).value or "0.15"),
                leverage_warning=float(self.query_one("#leverage-warning", Input).value or "2.0"),
                data_source=data_source,
                cache_dir=self.query_one("#cache-dir", Input).value,
                export_dir=self.query_one("#export-dir", Input).value,
            )
            save_settings(s)
            self.notify("Settings saved.")
