from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal


class HeaderBar(QWidget):
    close_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.setFixedHeight(36)
        self.setStyleSheet("QWidget { background: rgba(255,255,255,0.04); border-radius: 14px 14px 0 0; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        icon = QLabel("◈")
        icon.setStyleSheet("color: rgba(120,200,255,0.9); font-size:14px; background:transparent;")
        layout.addWidget(icon)

        title = QLabel("STEALTH OVERLAY")
        title.setStyleSheet("""
            color: rgba(255,255,255,0.5);
            font-size: 9px;
            font-family: 'Consolas', monospace;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)
        layout.addWidget(title)
        layout.addStretch()

        for text, color, sig in [
            ("─", "rgba(255,200,50,0.8)", self.minimize_clicked),
            ("✕", "rgba(255,80,80,0.8)",  self.close_clicked),
        ]:
            btn = QPushButton(text)
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.07); color: {color};
                    border: none; border-radius: 11px; font-size:11px; font-weight:bold;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.18); }}
            """)
            btn.clicked.connect(sig)
            layout.addWidget(btn)
