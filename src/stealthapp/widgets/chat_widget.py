"""Twitch IRC + YouTube chat widget."""

from __future__ import annotations
import socket, threading, time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QTimer


_PLATFORM_COLOR = {"twitch": "#9147ff", "youtube": "#ff0000"}
_USER_COLORS = ["#ff6b6b","#feca57","#48dbfb","#ff9ff3","#54a0ff","#5f27cd","#01cbc6","#ff9f43"]


class _Signals(QObject):
    received = pyqtSignal(str, str, str)   # platform, user, msg


class _TwitchThread(threading.Thread):
    def __init__(self, channel: str, signals: _Signals, token="", bot=""):
        super().__init__(daemon=True)
        self.channel = channel.lower().lstrip("#")
        self.signals = signals
        self.token = token or "SCHMOOPIIE"
        self.bot = bot or "justinfan12345"
        self._stop = False

    def run(self):
        try:
            s = socket.socket(); s.connect(("irc.chat.twitch.tv", 6667)); s.settimeout(5)
            def send(m): s.send((m+"\r\n").encode())
            send(f"PASS oauth:{self.token}" if self.token != "SCHMOOPIIE" else "PASS SCHMOOPIIE")
            send(f"NICK {self.bot}"); send(f"JOIN #{self.channel}")
            buf = ""
            while not self._stop:
                try:
                    buf += s.recv(2048).decode("utf-8", errors="ignore")
                    while "\r\n" in buf:
                        line, buf = buf.split("\r\n", 1)
                        if "PRIVMSG" in line:
                            try:
                                user = line.split("!")[0].lstrip(":")
                                msg  = line.split("PRIVMSG")[1].split(":",1)[1].strip()
                                self.signals.received.emit("twitch", user, msg)
                            except Exception: pass
                        elif line.startswith("PING"):
                            send("PONG :tmi.twitch.tv")
                except socket.timeout: pass
        except Exception as e:
            print(f"[Twitch] {e}")


class _YouTubeThread(threading.Thread):
    def __init__(self, video_id: str, signals: _Signals):
        super().__init__(daemon=True)
        self.video_id = video_id
        self.signals = signals
        self._stop = False

    def run(self):
        try:
            import pytchat  # type: ignore
            chat = pytchat.create(video_id=self.video_id)
            while not self._stop and chat.is_alive():
                for c in chat.get().sync_items():
                    self.signals.received.emit("youtube", c.author.name, c.message)
                time.sleep(1)
        except ImportError:
            print("[YouTube] pip install pytchat")
        except Exception as e:
            print(f"[YouTube] {e}")


class _Msg(QWidget):
    def __init__(self, platform, user, msg):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lo = QHBoxLayout(self); lo.setContentsMargins(8,2,8,2); lo.setSpacing(4)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{_PLATFORM_COLOR.get(platform,'#fff')};font-size:8px;background:transparent;")
        dot.setFixedWidth(12)
        lo.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        uc = _USER_COLORS[hash(user) % len(_USER_COLORS)]
        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background:transparent;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setText(f'<span style="color:{uc};font-weight:bold;font-size:11px;">{user}</span>'
                    f'<span style="color:rgba(255,255,255,0.7);font-size:11px;"> {msg}</span>')
        lo.addWidget(lbl, 1)


class ChatWidget(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._max = config.get("max_chat_messages", 60)
        self._count = 0
        self._sig = _Signals()
        self._sig.received.connect(self._on_msg)
        self._threads: list = []
        self._build()
        self._connect()

    def _build(self):
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)

        hdr = QWidget(); hdr.setStyleSheet("background:rgba(255,255,255,0.03);")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,5,12,5)
        lbl = QLabel("LIVE CHAT")
        lbl.setStyleSheet("color:rgba(255,255,255,0.35);font-size:9px;font-family:'Consolas',monospace;letter-spacing:2px;background:transparent;")
        hl.addWidget(lbl); hl.addStretch()

        self._tw_dot = QLabel("● Twitch")
        self._tw_dot.setStyleSheet("color:rgba(145,71,255,0.35);font-size:9px;background:transparent;")
        self._yt_dot = QLabel("● YouTube")
        self._yt_dot.setStyleSheet("color:rgba(255,0,0,0.35);font-size:9px;background:transparent;margin-left:6px;")
        hl.addWidget(self._tw_dot); hl.addWidget(self._yt_dot)
        lo.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(180)
        self._scroll.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:rgba(255,255,255,0.05);width:4px;border-radius:2px;}
            QScrollBar::handle:vertical{background:rgba(255,255,255,0.2);border-radius:2px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)

        self._container = QWidget(); self._container.setStyleSheet("background:transparent;")
        self._clo = QVBoxLayout(self._container)
        self._clo.setContentsMargins(0,4,0,4); self._clo.setSpacing(0)
        self._clo.addStretch()

        self._placeholder = QLabel("No chat connected.\nSet twitch_channel or youtube_video_id in config.json")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color:rgba(255,255,255,0.18);font-size:10px;font-family:'Consolas',monospace;padding:16px;background:transparent;")
        self._clo.insertWidget(0, self._placeholder)
        self._scroll.setWidget(self._container)
        lo.addWidget(self._scroll)

    def _connect(self):
        connected = False
        if self.config.get("twitch_enabled") and self.config.get("twitch_channel"):
            t = _TwitchThread(self.config.get("twitch_channel"), self._sig,
                              self.config.get("twitch_token",""), self.config.get("twitch_bot_name",""))
            t.start(); self._threads.append(t)
            self._tw_dot.setStyleSheet("color:rgba(145,71,255,0.9);font-size:9px;background:transparent;")
            connected = True
        if self.config.get("youtube_enabled") and self.config.get("youtube_video_id"):
            t = _YouTubeThread(self.config.get("youtube_video_id"), self._sig)
            t.start(); self._threads.append(t)
            self._yt_dot.setStyleSheet("color:rgba(255,0,0,0.9);font-size:9px;background:transparent;margin-left:6px;")
            connected = True
        if connected:
            self._placeholder.hide()

    @pyqtSlot(str, str, str)
    def _on_msg(self, platform, user, msg):
        if self._placeholder.isVisible(): self._placeholder.hide()
        if self._count >= self._max:
            item = self._clo.itemAt(0)
            if item and item.widget(): item.widget().deleteLater()
            else: self._clo.takeAt(0)
            self._count -= 1
        self._clo.insertWidget(self._clo.count()-1, _Msg(platform, user, msg))
        self._count += 1
        QTimer.singleShot(40, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))
