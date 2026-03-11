from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PyQt6.QtCore import Qt, pyqtSlot

_KEY = "color:rgba(150,200,255,0.6);font-size:10px;font-family:'Consolas',monospace;letter-spacing:1px;background:transparent;"
_VAL = "color:rgba(255,255,255,0.95);font-size:15px;font-family:'Consolas',monospace;font-weight:bold;background:transparent;"
_GAME = "color:rgba(120,200,255,0.7);font-size:10px;font-family:'Consolas',monospace;letter-spacing:2px;padding:6px 12px 2px;background:transparent;"


class _Card(QWidget):
    def __init__(self, k, v):
        super().__init__()
        self.setStyleSheet("QWidget{background:rgba(255,255,255,0.04);border-radius:6px;}")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(8,6,8,6); lo.setSpacing(2)
        self._k = QLabel(k.upper()); self._k.setStyleSheet(_KEY); self._k.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._v = QLabel(str(v));     self._v.setStyleSheet(_VAL); self._v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(self._k); lo.addWidget(self._v)

    def set(self, v): self._v.setText(str(v))


class StatPanel(QWidget):
    def __init__(self, config):
        super().__init__()
        self._cards: dict[str, _Card] = {}
        lo = QVBoxLayout(self)
        lo.setContentsMargins(10,4,10,8); lo.setSpacing(6)
        self.setStyleSheet("background:transparent;")

        self._game_lbl = QLabel("OVERLAY")
        self._game_lbl.setStyleSheet(_GAME)
        lo.addWidget(self._game_lbl)

        self._grid_w = QWidget(); self._grid_w.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_w)
        self._grid.setContentsMargins(0,0,0,0); self._grid.setSpacing(6)
        lo.addWidget(self._grid_w)

        self._custom_w = QWidget(); self._custom_w.setStyleSheet("background:transparent;")
        self._custom_lo = QVBoxLayout(self._custom_w)
        self._custom_lo.setContentsMargins(0,0,0,0); self._custom_lo.setSpacing(2)
        lo.addWidget(self._custom_w)

    def _clear_grid(self):
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w: w.deleteLater()
        self._cards.clear()

    def _clear_custom(self):
        for i in reversed(range(self._custom_lo.count())):
            w = self._custom_lo.itemAt(i).widget()
            if w: w.deleteLater()

    @pyqtSlot(dict)
    def update_stats(self, data: dict):
        self._game_lbl.setText(data.get("game","").upper() or "OVERLAY")

        stats = data.get("stats", {})
        self._clear_grid()
        for idx, (k, v) in enumerate(stats.items()):
            card = _Card(k, v)
            self._cards[k] = card
            self._grid.addWidget(card, *divmod(idx, 3))

        custom = data.get("custom", [])
        self._clear_custom()
        for item in custom:
            row = QWidget(); row.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row); rl.setContentsMargins(4,0,4,0)
            kl = QLabel(str(item.get("key","")).upper()); kl.setStyleSheet(_KEY)
            vl = QLabel(str(item.get("value",""))); vl.setStyleSheet(_VAL)
            vl.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            rl.addWidget(kl); rl.addStretch(); rl.addWidget(vl)
            self._custom_lo.addWidget(row)
