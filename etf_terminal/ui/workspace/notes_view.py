"""Notes view - research notes per ETF or portfolio."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Input, Button, TextArea, DataTable
from textual.containers import VerticalScroll

from etf_terminal.db.database import save_note, get_notes, delete_note, Note


class NotesView(VerticalScroll):
    DEFAULT_CSS = """
    NotesView {
        padding: 1 2;
    }
    NotesView TextArea {
        height: 10;
    }
    NotesView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Notes[/bold]")
        with Horizontal():
            yield Input(placeholder="Target (e.g. VTI, portfolio)", id="note-target")
            yield Button("Save", id="note-save")
            yield Button("Delete Selected", id="note-delete")
        yield TextArea(id="note-editor")
        yield DataTable(id="notes-table")

    def on_mount(self) -> None:
        table = self.query_one("#notes-table", DataTable)
        table.add_columns("ID", "Target", "Preview", "Updated")
        table.cursor_type = "row"
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "note-save":
            target = self.query_one("#note-target", Input).value.strip() or "general"
            content = self.query_one("#note-editor", TextArea).text
            if content.strip():
                note = Note(target_type="etf", target_id=target, content=content)
                save_note(note)
                self.query_one("#note-editor", TextArea).clear()
                self._refresh()
        elif event.button.id == "note-delete":
            table = self.query_one("#notes-table", DataTable)
            if table.cursor_row is not None:
                row = table.get_row_at(table.cursor_row)
                if row:
                    delete_note(int(row[0]))
                    self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#notes-table", DataTable)
        table.clear()
        for n in get_notes():
            preview = n.content[:40].replace("\n", " ")
            table.add_row(str(n.id), n.target_id, preview, n.updated_at[:10])
