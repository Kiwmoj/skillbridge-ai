from __future__ import annotations

import json
import os
import hashlib
import shutil
from functools import partial
from pathlib import Path
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QDesktopServices, QFont, QFontDatabase, QPixmap
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLayout, QLabel, QLineEdit, QMainWindow,
    QInputDialog, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from components.cards import Card, add_title, badge, heading
from components.charts import ChartCanvas
from components.progress_widgets import SkillProgress, roadmap_progress
from components.sidebar import Sidebar
from database.db_manager import Database
from services.career_service import CareerService
from services.career_catalog import CAREERS_BY_INDUSTRY, CAREER_NAMES, INDUSTRIES, infer_industry
from services.api_client import ApiClient, ApiError
from services.gemini_service import GeminiService
from services.session_store import SessionStore
from services.portfolio_service import PortfolioService
from services.roadmap_service import RoadmapService
from workers.ai_worker import AIWorker


NAV = {
    "Overview": 0, "Career reality check": 1, "Skill gap": 2,
    "Portfolio review": 3, "Learning roadmap": 4, "Project studio": 5,
    "Career explorer": 6, "Progress analytics": 7, "My profile": 8,
    "Opportunities & Colleges": 9,
}

QSS = """
* { font-family: 'Arial'; color: #e7edf7; }
QMainWindow, QWidget#appRoot, QStackedWidget { background: #0e1420; }
QWidget#pageBody, QScrollArea, QScrollArea::viewport { background: #0e1420; }
QFrame#sidebar { background: #111927; border-right: 1px solid #202c3e; }
QLabel#brandMark { background: #3979e8; color: white; border-radius: 12px; font-weight: 800; font-size: 15px; qproperty-alignment: AlignCenter; }
QLabel#brandName { font-size: 17px; font-weight: 700; color: #f4f7fc; }
QLabel#eyebrow { color: #8391a7; font-size: 9px; font-weight: 700; letter-spacing: 1.3px; }
QPushButton#navButton { background: transparent; border: 0; border-radius: 9px; color: #98a6bb; text-align: left; padding: 11px 12px; font-size: 12px; }
QPushButton#navButton:hover { background: #1b2638; color: #eff5ff; }
QPushButton#navButton:checked { background: #1d3152; color: #75b3ff; font-weight: 700; }
QFrame#topBar { background: #0e1420; border-bottom: 1px solid #202c3e; }
QLabel#topTitle { color: #f3f6fc; font-weight: 700; font-size: 16px; }
QLabel#statusText { color: #a9b8cd; font-size: 10px; }
QFrame#card, QFrame#accentCard { background: #151c2b; border: 1px solid #222e42; border-radius: 13px; }
QFrame#accentCard { background: #17243a; border-color: #29476f; }
QLabel#pageTitle { color: #f2f6fc; font-size: 28px; font-weight: 750; }
QLabel#cardTitle { color: #eff4fc; font-size: 14px; font-weight: 700; }
QLabel#body { color: #d7e0ef; font-size: 12px; }
QLabel#muted { color: #93a2b8; font-size: 11px; }
QLabel#statValue { color: #f5f8fd; font-size: 25px; font-weight: 750; }
QLabel#statLabel { color: #94a4ba; font-size: 10px; }
QLabel#badge_blue, QLabel#badge_purple, QLabel#badge_green, QLabel#badge_gold, QLabel#badge_gray { border-radius: 9px; font-size: 9px; font-weight: 700; }
QLabel#badge_blue { background: #1a3356; color: #78b8ff; } QLabel#badge_purple { background: #322644; color: #cda8ff; }
QLabel#badge_green { background: #1c352f; color: #73d8b0; } QLabel#badge_gold { background: #3a3021; color: #edc782; }
QLabel#badge_gray { background: #242d3c; color: #aab7c9; }
QPushButton { background: #27364b; color: #e9f1fc; border: 1px solid #354761; border-radius: 8px; padding: 9px 13px; font-weight: 650; font-size: 11px; }
QPushButton:hover { background: #324865; border-color: #4c6a91; }
QPushButton:disabled { color: #76859b; background: #202b3b; border-color: #263245; }
QPushButton#primaryButton { background: #3979e8; border-color: #3979e8; color: white; }
QPushButton#primaryButton:hover { background: #4b8bf5; }
QPushButton#quietButton { background: transparent; border-color: #344259; }
QLineEdit, QTextEdit, QComboBox, QSpinBox { background: #101725; border: 1px solid #2b394f; border-radius: 7px; padding: 8px 9px; color: #e7edf7; selection-background-color: #3979e8; font-size: 11px; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { background: #151c2b; border: 1px solid #344259; selection-background-color: #284b7b; }
QTextEdit { padding: 9px; }
QProgressBar { background: #222c3d; border: none; border-radius: 7px; color: #cad7e9; text-align: center; font-size: 9px; }
QProgressBar::chunk { background: #4a91f3; border-radius: 7px; }
QProgressBar#skillProgress::chunk { background: #52a5ff; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #111927; width: 9px; margin: 3px; }
QScrollBar::handle:vertical { background: #35445a; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QCheckBox { color: #d7e0ef; spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QDialog { background: #111927; }
"""

_FONT_READY = False


def register_ui_font():
    global _FONT_READY
    if _FONT_READY:
        return
    app = QApplication.instance()
    if app:
        windows_font = Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
        if windows_font.exists():
            QFontDatabase.addApplicationFont(str(windows_font))
        app.setFont(QFont("Arial", 10))
    _FONT_READY = True


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def display_timestamp(value: str) -> str:
    """Convert SQLite UTC timestamps to the computer's local timezone."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%b %d · %I:%M %p")
    except (TypeError, ValueError):
        return value


def make_button(text: str, primary=False, quiet=False) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("primaryButton" if primary else "quietButton" if quiet else "")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def make_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    body.setObjectName("pageBody")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(30, 26, 30, 32)
    layout.setSpacing(16)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    scroll.setWidget(body)
    scroll.body = body
    scroll.body_layout = layout
    return scroll, layout


class MainWindow(QMainWindow):
    def __init__(self, db: Database | None = None):
        super().__init__()
        register_ui_font()
        self._db_injected = db is not None
        self.db = db or Database()
        self.api_client = ApiClient()
        self.session_store = SessionStore()
        saved_token, saved_user = self.session_store.load()
        self.api_client.token = saved_token
        if saved_token and saved_user and not self._db_injected:
            self._bind_database_to_user(saved_user)
        self.gemini = GeminiService(self.api_client)
        self.career_service = CareerService(self.gemini)
        self.portfolio_service = PortfolioService(self.gemini)
        self.roadmap_service = RoadmapService(self.gemini)
        self._workers: set[AIWorker] = set()
        self.current_image = ""
        self.generated_projects: list[dict] = []
        self.career_report: dict | None = None
        self.setWindowTitle("SkillBridge AI · Turn your ambition into a career")
        self.setMinimumSize(QSize(1200, 750))
        self.resize(1440, 900)
        self.setStyleSheet(QSS)
        self._build_shell()
        self._build_pages()
        if self.gemini.enabled:
            self.navigate("Overview" if self.db.has_profile() else "Student setup")
        else:
            self.sidebar.hide()
            self.profile_button.hide()
            self.navigate("Service & account")

    def _build_shell(self):
        root = QWidget()
        root.setObjectName("appRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigate)
        shell.addWidget(self.sidebar)
        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(0)
        top = QFrame()
        top.setObjectName("topBar")
        top.setFixedHeight(58)
        top_box = QHBoxLayout(top)
        top_box.setContentsMargins(26, 0, 25, 0)
        self.header_title = QLabel("Overview")
        self.header_title.setObjectName("topTitle")
        top_box.addWidget(self.header_title)
        top_box.addStretch(1)
        self.mode_label = badge("SKILLBRIDGE CONNECTED" if self.gemini.enabled else "SERVICE SIGN IN REQUIRED", "green" if self.gemini.enabled else "gold")
        top_box.addWidget(self.mode_label)
        self.status_label = QLabel("Student data is saved locally")
        self.status_label.setObjectName("statusText")
        top_box.addWidget(self.status_label)
        self.profile_button = make_button("My profile", quiet=True)
        self.profile_button.clicked.connect(lambda: self.navigate("My profile"))
        top_box.addWidget(self.profile_button)
        right_box.addWidget(top)
        self.stack = QStackedWidget()
        right_box.addWidget(self.stack, 1)
        shell.addWidget(right, 1)
        self.setCentralWidget(root)

    def _build_pages(self):
        self.pages: dict[str, QWidget] = {}
        builders = [
            ("Overview", self._page_dashboard),
            ("Career reality check", self._page_career),
            ("Skill gap", self._page_skills),
            ("Portfolio review", self._page_portfolio),
            ("Learning roadmap", self._page_roadmap),
            ("Project studio", self._page_projects),
            ("Career explorer", self._page_explorer),
            ("Opportunities & Colleges", self._page_opportunities),
            ("Progress analytics", self._page_analytics),
            ("My profile", self._page_profile),
            ("Service & account", self._page_gemini_setup),
            ("Student setup", self._page_student_setup),
        ]
        for name, builder in builders:
            widget = builder()
            self.pages[name] = widget
            self.stack.addWidget(widget)
        self._update_gemini_auth_ui()

    def navigate(self, name: str):
        if name not in self.pages:
            return
        self.sidebar.set_active(name)
        self.stack.setCurrentWidget(self.pages[name])
        self.header_title.setText(name)
        self._refresh_dynamic(name)
        if name in {"Student setup", "Service & account"}:
            self.sidebar.hide(); self.profile_button.hide()
        else:
            self.sidebar.show(); self.profile_button.show()

    def _refresh_dynamic(self, name):
        if name == "Overview":
            self._refresh_dashboard()
        elif name == "Learning roadmap":
            self._refresh_roadmap()
        elif name == "Project studio":
            self._refresh_saved_projects()
        elif name == "Portfolio review":
            self._refresh_review_history()
            self.portfolio_category.setText(self.db.get_profile().career_goal)
        elif name == "Progress analytics":
            self._refresh_analytics()
        elif name == "Opportunities & Colleges":
            self._load_saved_opportunities()
        elif name == "Skill gap":
            self._refresh_skill_chart()
        elif name == "My profile":
            self._load_profile_fields()
        elif name == "Career reality check":
            profile = self.db.get_profile()
            self.career_goal_input.setCurrentText(profile.career_goal)
            self.career_industry.setCurrentText(profile.industry)
        elif name == "Career explorer":
            profile = self.db.get_profile()
            self.career_a.setCurrentText(profile.career_goal)
            self.career_a_industry.setCurrentText(profile.industry)
        if self.db.has_profile(): self.profile_button.setText(self.db.get_profile().name)

    def _card(self, title: str | None = None, subtitle: str = "", accent=False) -> Card:
        card = Card(accent=accent)
        if title:
            add_title(card, title, subtitle)
        return card

    @staticmethod
    def _career_picker(value: str = "") -> QComboBox:
        picker = QComboBox()
        picker.setEditable(True)
        picker.addItems(CAREER_NAMES)
        picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        picker.setCurrentText(value)
        completer = QCompleter(CAREER_NAMES, picker)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        picker.setCompleter(completer)
        picker.setMinimumWidth(220)
        return picker

    @staticmethod
    def _industry_picker(value: str = "") -> QComboBox:
        picker = QComboBox()
        picker.addItems(INDUSTRIES)
        picker.setCurrentText(value if value in INDUSTRIES else "Other / custom")
        return picker

    @staticmethod
    def _profile_payload(profile):
        return {"name":profile.name, "career_goal":profile.career_goal, "industry":profile.industry,
                "education_level":profile.education_level, "experience":profile.experience,
                "existing_skills":profile.existing_skills or [], "interests":profile.interests,
                "age_range":profile.age_range, "institution":profile.institution, "country":profile.country,
                "region":profile.region, "career_interests":profile.career_interests or [],
                "areas_to_improve":profile.areas_to_improve or [],
                "learning_preferences":profile.learning_preferences, "weekly_availability":profile.weekly_availability,
                "short_term_goal":profile.short_term_goal, "long_term_goal":profile.long_term_goal}

    def _latest_recommendation(self, kind: str) -> dict:
        items = self.db.get_recommendations(self.db.get_profile().career_goal, kind)
        return items[0]["content"] if items else {}

    def _persist_remote_record(self, kind: str, key: str, payload: dict) -> None:
        if not self.api_client.authenticated:
            return
        worker = AIWorker(self.api_client.save_record, kind, key, payload)
        self._workers.add(worker)
        worker.succeeded.connect(lambda _result: None)
        worker.failed.connect(lambda error: self._notify(f"Saved locally · cloud sync unavailable: {error}"))
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        worker.start()

    def _save_recommendation(self, career: str, industry: str, kind: str, content: dict,
                             source_mode: str = "LIVE GEMINI API") -> int:
        record_id = self.db.add_recommendation(career, industry, kind, content, source_mode)
        self._persist_remote_record("assessment", str(record_id),
                                    {"career_goal": career, "industry": industry, "kind": kind,
                                     "source_mode": source_mode, "content": content})
        return record_id

    def _set_source_mode(self, source_mode: str) -> None:
        self.mode_label.setText("LIVE GEMINI RESPONSE" if "LIVE GEMINI" in source_mode else source_mode)
        self.status_label.setText(f"{source_mode} · saved on this device")

    def _bind_database_to_user(self, user: dict) -> None:
        """Give each service account its own local SQLite file."""
        if self._db_injected:
            return
        user_id = str(user.get("id") or "").strip()
        if not user_id:
            return
        data_root = self.db.path.parent
        owner_path = data_root / "local_db_owner.json"
        accounts = data_root / "accounts"
        accounts.mkdir(parents=True, exist_ok=True)
        owner = ""
        try:
            owner = str(json.loads(owner_path.read_text(encoding="utf-8")).get("user_id") or "")
        except (OSError, ValueError, AttributeError):
            pass
        account_id = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]
        account_path = accounts / f"{account_id}.sqlite3"
        # If this installation already had private local work, attach it to only
        # the first authenticated service account. Other accounts get an empty DB.
        if not owner and self.db.path.exists() and not account_path.exists():
            shutil.copy2(self.db.path, account_path)
            try:
                wal = Path(str(self.db.path) + "-wal")
                if wal.exists():
                    shutil.copy2(wal, Path(str(account_path) + "-wal"))
            except OSError:
                pass
            owner_path.write_text(json.dumps({"user_id": user_id}), encoding="utf-8")
        self.db = Database(account_path)

    def _sync_profile_with_service(self, pull_if_empty: bool = False) -> None:
        if not self.api_client.authenticated:
            return
        local_profile = self.db.get_profile()
        try:
            remote = self.api_client.get_profile()
            if pull_if_empty and not self.db.has_profile() and remote.get("career_goal"):
                self.db.save_profile(remote.get("name", "Student"), remote["career_goal"],
                                     remote.get("education_level", ""), remote.get("experience", "Beginner"),
                                     remote.get("existing_skills", []), remote.get("industry", "Other / custom"),
                                     interests=remote.get("interests", []), age_range=remote.get("age_range", ""),
                                     institution=remote.get("institution", ""), country=remote.get("country", ""),
                                     region=remote.get("region", ""), career_interests=remote.get("career_interests", []),
                                     areas_to_improve=remote.get("areas_to_improve", []),
                                     learning_preferences=remote.get("learning_preferences", ""),
                                     weekly_availability=remote.get("weekly_availability", ""),
                                     short_term_goal=remote.get("short_term_goal", ""),
                                     long_term_goal=remote.get("long_term_goal", ""))
            elif self.db.has_profile():
                self.api_client.save_profile(self._profile_payload(local_profile))
        except ApiError as exc:
            self.status_label.setText(f"Profile saved locally · service sync unavailable: {exc}")

    def _accept_account_session(self, auth: dict) -> None:
        self.api_client.token = auth["access_token"]
        user = auth["user"]
        self.session_store.save(self.api_client.token, user)
        self._bind_database_to_user(user)
        self._sync_profile_with_service(pull_if_empty=True)
        self._update_gemini_auth_ui("Signed in. AI actions are sent to the service; Gemini must also be configured by the service owner.")
        if self.db.has_profile():
            self.sidebar.show(); self.profile_button.show()
            self.profile_button.setText(self.db.get_profile().name)
            self.navigate("Overview")
        else:
            self.sidebar.hide(); self.profile_button.hide()
            self.navigate("Student setup")

    def _connect_service(self):
        try:
            self.api_client.save_base_url(self.api_url_input.text())
            state = self.api_client.health()
        except ApiError as exc:
            self.backend_status.setText(str(exc))
            return
        ai = "Gemini configured" if state.get("ai_configured") else "Gemini not configured by the service owner"
        search = "live opportunity search configured" if state.get("live_search_configured") else "live opportunity search unavailable"
        self.backend_status.setText(f"Service reachable · {ai} · {search}")

    def _account_action(self, create: bool = False):
        try:
            if not self.api_client.configured:
                self.api_client.save_base_url(self.api_url_input.text())
            if create:
                auth = self.api_client.register(self.account_email.text(), self.account_name.text(), self.account_password.text())
            else:
                auth = self.api_client.login(self.account_email.text(), self.account_password.text())
        except ApiError as exc:
            self.backend_status.setText(str(exc))
            return
        self.account_password.clear()
        self._accept_account_session(auth)

    def _request_password_reset(self):
        try:
            if not self.api_client.configured:
                self.api_client.save_base_url(self.api_url_input.text())
            self.api_client.request_password_reset(self.account_email.text())
            self.backend_status.setText("If the account exists, the service sent a reset code to its email address.")
        except ApiError as exc:
            self.backend_status.setText(str(exc))

    def _confirm_password_reset(self):
        try:
            if not self.api_client.configured:
                self.api_client.save_base_url(self.api_url_input.text())
            self.api_client.confirm_password_reset(self.reset_code.text(), self.new_password.text())
            self.reset_code.clear(); self.new_password.clear()
            self.backend_status.setText("Password updated. Sign in with your new password.")
        except ApiError as exc:
            self.backend_status.setText(str(exc))

    def _sign_out(self):
        try:
            if self.api_client.authenticated:
                self.api_client.logout()
        except ApiError:
            pass
        self.api_client.token = ""
        self.session_store.clear()
        self._update_gemini_auth_ui("Signed out. Your saved data remains in this device's account-scoped SQLite database.")
        self.sidebar.hide(); self.profile_button.hide()
        self.navigate("Service & account")

    def _delete_account(self):
        if not self.api_client.authenticated:
            return
        confirmation = QMessageBox.question(self, "Delete SkillBridge account",
            "Permanently delete this account and its server records, and remove its local account database? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api_client.delete_account(self.account_email.text(), self.account_password.text())
        except ApiError as exc:
            self.backend_status.setText(str(exc))
            return
        self.account_password.clear()
        if not self._db_injected:
            for suffix in ("", "-wal", "-shm"):
                try:
                    Path(str(self.db.path) + suffix).unlink(missing_ok=True)
                except OSError:
                    pass
        self.api_client.token = ""
        self.session_store.clear()
        self.sidebar.hide(); self.profile_button.hide()
        self._update_gemini_auth_ui("Account deleted. Its server records and this device's account database were removed.")
        self.navigate("Service & account")

    def _apply_career_selection(self, goal: str, industry: str = "") -> None:
        """Persist the selected career as the single source used by career workflows."""
        profile = self.db.get_profile()
        clean_goal = goal.strip()
        if not clean_goal: return
        clean_industry = infer_industry(clean_goal, industry or profile.industry)
        if clean_goal != profile.career_goal or clean_industry != profile.industry:
            current_skills = list(dict.fromkeys((profile.existing_skills or []) + [skill.name for skill in self.db.get_skills(profile.career_goal)]))
            self.db.save_profile(profile.name, clean_goal, profile.education_level, profile.experience,
                                 current_skills, industry=clean_industry, interests=profile.interests,
                                 age_range=profile.age_range, institution=profile.institution, country=profile.country,
                                 region=profile.region, career_interests=profile.career_interests or [],
                                 areas_to_improve=profile.areas_to_improve or [], learning_preferences=profile.learning_preferences,
                                 weekly_availability=profile.weekly_availability, short_term_goal=profile.short_term_goal,
                                 long_term_goal=profile.long_term_goal)
            self._sync_profile_with_service()
            if hasattr(self, "profile_goal"):
                self.profile_goal.setCurrentText(clean_goal)
            if hasattr(self, "profile_industry"):
                self.profile_industry.setCurrentText(clean_industry)
            if hasattr(self, "career_goal_input"):
                self.career_goal_input.setCurrentText(clean_goal)
            if hasattr(self, "career_industry"):
                self.career_industry.setCurrentText(clean_industry)
            if hasattr(self, "career_a"):
                self.career_a.setCurrentText(clean_goal)
                self.career_a_industry.setCurrentText(clean_industry)
            self._populate_skill_rows()
            self._refresh_skill_chart()
            self._refresh_roadmap()
            self._refresh_dashboard()
            self._refresh_analytics()
        self.profile_button.setText(profile.name)

    def _stat_card(self, value: str, label: str, note: str = "") -> Card:
        card = Card()
        v = QLabel(value); v.setObjectName("statValue")
        l = QLabel(label.upper()); l.setObjectName("statLabel")
        card.layout_box.addWidget(v); card.layout_box.addWidget(l)
        if note: card.layout_box.addWidget(heading(note, "muted"))
        return card

    def _bullet_group(self, title: str, values, tone="blue") -> Card:
        card = self._card(title)
        if not values:
            card.layout_box.addWidget(heading("No recommendations yet.", "muted"))
        for item in values:
            if isinstance(item, dict):
                name = item.get("name", "Recommendation")
                why = item.get("why", "")
                row = QVBoxLayout(); row.setSpacing(3)
                top = QHBoxLayout(); top.addWidget(badge(name, tone), 0); top.addStretch(1); row.addLayout(top)
                if why: row.addWidget(heading(why))
                card.layout_box.addLayout(row)
            else:
                card.layout_box.addWidget(heading(f"•  {item}"))
        return card

    def _page_student_setup(self):
        page, layout = make_page()
        layout.addStretch(1)
        layout.addWidget(heading("Set up your student profile", "title"), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(heading("Your career and background guide every recommendation. You can enter any career.", "muted"), 0, Qt.AlignmentFlag.AlignHCenter)
        card = self._card("About you", "Saved in your account profile and this device’s SQLite database", accent=True)
        form = QFormLayout(); form.setSpacing(14)
        self.setup_name = QLineEdit(); self.setup_name.setPlaceholderText("Your name")
        self.setup_age = QLineEdit(); self.setup_age.setPlaceholderText("Age range, e.g. 16–18 (optional)")
        self.setup_education = QLineEdit(); self.setup_education.setPlaceholderText("For example, high school, college, or self-taught")
        self.setup_institution = QLineEdit(); self.setup_institution.setPlaceholderText("School or institution (optional)")
        self.setup_country = QLineEdit(); self.setup_country.setPlaceholderText("Country")
        self.setup_region = QLineEdit(); self.setup_region.setPlaceholderText("Region or state (optional)")
        self.setup_career = self._career_picker(); self.setup_career.setPlaceholderText("Search or type any career")
        self.setup_industry = self._industry_picker()
        self.setup_experience = QComboBox(); self.setup_experience.addItems(["Beginner", "Intermediate", "Advanced"])
        self.setup_skills = QLineEdit(); self.setup_skills.setPlaceholderText("Comma-separated skills you already have")
        self.setup_interests = QLineEdit(); self.setup_interests.setPlaceholderText("Comma-separated interests")
        self.setup_career_interests = QLineEdit(); self.setup_career_interests.setPlaceholderText("Other career interests (comma separated)")
        self.setup_improvement = QLineEdit(); self.setup_improvement.setPlaceholderText("Skills or areas you want to improve")
        self.setup_preferences = QLineEdit(); self.setup_preferences.setPlaceholderText("For example, visual lessons, reading, hands-on practice")
        self.setup_availability = QLineEdit(); self.setup_availability.setPlaceholderText("Hours per week")
        self.setup_short_goal = QLineEdit(); self.setup_short_goal.setPlaceholderText("Short-term learning goal")
        self.setup_long_goal = QLineEdit(); self.setup_long_goal.setPlaceholderText("Long-term goal")
        form.addRow("Name", self.setup_name); form.addRow("Age range", self.setup_age); form.addRow("Education", self.setup_education)
        form.addRow("School / institution", self.setup_institution); form.addRow("Country", self.setup_country); form.addRow("Region", self.setup_region)
        form.addRow("Career goal", self.setup_career); form.addRow("Industry", self.setup_industry)
        form.addRow("Other career interests", self.setup_career_interests); form.addRow("Interests", self.setup_interests)
        form.addRow("Experience level", self.setup_experience); form.addRow("Existing skills", self.setup_skills)
        form.addRow("Areas to improve", self.setup_improvement); form.addRow("Learning preferences", self.setup_preferences)
        form.addRow("Weekly availability", self.setup_availability); form.addRow("Short-term goal", self.setup_short_goal); form.addRow("Long-term goal", self.setup_long_goal)
        card.layout_box.addLayout(form)
        self.setup_save_button = make_button("Save profile and continue", primary=True)
        self.setup_save_button.clicked.connect(self._create_profile)
        card.layout_box.addWidget(self.setup_save_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(card)
        layout.addWidget(heading("AI requests use the SkillBridge service after you sign in. Students never enter Gemini credentials.", "muted"), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return page

    def _create_profile(self):
        try:
            skills = [value.strip() for value in self.setup_skills.text().split(",") if value.strip()]
            interests = [value.strip() for value in self.setup_interests.text().split(",") if value.strip()]
            career_interests = [value.strip() for value in self.setup_career_interests.text().split(",") if value.strip()]
            areas = [value.strip() for value in self.setup_improvement.text().split(",") if value.strip()]
            self.db.save_profile(self.setup_name.text(), self.setup_career.currentText(), self.setup_education.text().strip(),
                                 self.setup_experience.currentText(), skills, self.setup_industry.currentText(), interests,
                                 age_range=self.setup_age.text(), institution=self.setup_institution.text(),
                                 country=self.setup_country.text(), region=self.setup_region.text(),
                                 career_interests=career_interests, areas_to_improve=areas,
                                 learning_preferences=self.setup_preferences.text(), weekly_availability=self.setup_availability.text(),
                                 short_term_goal=self.setup_short_goal.text(), long_term_goal=self.setup_long_goal.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Profile needs attention", str(exc)); return
        self.profile_button.setText(self.db.get_profile().name)
        self.sidebar.show(); self.profile_button.show()
        self._sync_profile_with_service()
        self.navigate("Overview")

    def _page_gemini_setup(self):
        page, layout = make_page()
        layout.addWidget(heading("Service & account", "title"))
        card = self._card("SkillBridge service", "The service owner manages Gemini and search credentials on the backend", accent=True)
        card.layout_box.addWidget(heading("Students do not need a Gemini API key. Configure the HTTPS service URL, then sign in or create an account. For local development, http://127.0.0.1 is accepted."))
        self.api_url_input = QLineEdit(self.api_client.base_url)
        self.api_url_input.setPlaceholderText("https://your-skillbridge-service.example")
        card.layout_box.addWidget(self.api_url_input)
        connect_button = make_button("Connect to service", primary=True)
        connect_button.clicked.connect(self._connect_service)
        card.layout_box.addWidget(connect_button, 0, Qt.AlignmentFlag.AlignRight)
        self.backend_status = heading("No service connection has been checked.", "muted")
        card.layout_box.addWidget(self.backend_status)
        form = QFormLayout(); form.setSpacing(10)
        self.account_name = QLineEdit(); self.account_name.setPlaceholderText("Display name (required for a new account)")
        self.account_email = QLineEdit(); self.account_email.setPlaceholderText("Email address")
        self.account_password = QLineEdit(); self.account_password.setPlaceholderText("Password · at least 10 characters for new accounts")
        self.account_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Name", self.account_name); form.addRow("Email", self.account_email); form.addRow("Password", self.account_password)
        card.layout_box.addLayout(form)
        actions = QHBoxLayout()
        login_button = make_button("Sign in", primary=True); login_button.clicked.connect(lambda: self._account_action(False))
        register_button = make_button("Create account"); register_button.clicked.connect(lambda: self._account_action(True))
        actions.addWidget(login_button); actions.addWidget(register_button); actions.addStretch(1)
        card.layout_box.addLayout(actions)
        reset_form = QFormLayout(); reset_form.setSpacing(8)
        self.reset_code = QLineEdit(); self.reset_code.setPlaceholderText("Reset code from your email")
        self.new_password = QLineEdit(); self.new_password.setPlaceholderText("New password · at least 10 characters")
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        reset_form.addRow("Reset code", self.reset_code); reset_form.addRow("New password", self.new_password)
        card.layout_box.addLayout(reset_form)
        reset_actions = QHBoxLayout()
        request_reset = make_button("Request password reset"); request_reset.clicked.connect(self._request_password_reset)
        confirm_reset = make_button("Set new password"); confirm_reset.clicked.connect(self._confirm_password_reset)
        reset_actions.addWidget(request_reset); reset_actions.addWidget(confirm_reset); reset_actions.addStretch(1)
        card.layout_box.addLayout(reset_actions)
        self.account_status = self.gemini_auth_status = heading("", "muted")
        card.layout_box.addWidget(self.gemini_auth_status)
        self.gemini_test_button = make_button("Test live Gemini connection", quiet=True)
        self.gemini_test_button._prior_text = "Test Gemini connection"
        self.gemini_test_button.clicked.connect(self._test_gemini_connection)
        self.sign_out_button = make_button("Sign out", quiet=True)
        self.sign_out_button.clicked.connect(self._sign_out)
        self.delete_account_button = make_button("Delete account", quiet=True)
        self.delete_account_button.clicked.connect(self._delete_account)
        account_actions = QHBoxLayout()
        account_actions.addWidget(self.gemini_test_button); account_actions.addWidget(self.sign_out_button)
        account_actions.addWidget(self.delete_account_button); account_actions.addStretch(1)
        card.layout_box.addLayout(account_actions)
        self.gemini_setup_card = card
        self._update_gemini_auth_ui()
        layout.addWidget(card)
        layout.addWidget(heading("The career explorer, reality check, skill gap analysis, roadmap, project ideas, and portfolio review all use one authenticated server-side Gemini integration. No AI samples are shown when the service is unavailable.", "muted"))
        layout.addStretch(1)
        return page

    def _update_gemini_auth_ui(self, message: str = ""):
        enabled = self.gemini.enabled
        if hasattr(self, "mode_label"):
            self.mode_label.setText("SERVICE ACCOUNT CONNECTED" if enabled else "SERVICE SIGN IN REQUIRED")
            self.mode_label.setObjectName("badge_green" if enabled else "badge_gold")
            self.mode_label.style().unpolish(self.mode_label)
            self.mode_label.style().polish(self.mode_label)
        if hasattr(self, "gemini_auth_status"):
            self.gemini_auth_status.setText(message or (
                f"Signed in as {getattr(self, 'account_email', None).text() if hasattr(self, 'account_email') and self.api_client.authenticated else 'your SkillBridge account'}. The Gemini credential remains on the backend."
                if enabled else
                "Connect to a SkillBridge backend and sign in. The service owner must configure Gemini before real AI responses are available."
            ))
            self.gemini_test_button.setEnabled(enabled)
            self.sign_out_button.setEnabled(enabled)
            self.delete_account_button.setEnabled(enabled)
        for attribute in ("career_button", "skill_guidance_button", "portfolio_review_button", "adapt_button",
                          "roadmap_generate_button", "project_generate_button", "compare_button"):
            button = getattr(self, attribute, None)
            if button:
                button.setEnabled(enabled)
                if not enabled:
                    button.setToolTip("Sign in to the configured SkillBridge service to use Gemini features.")
                else:
                    button.setToolTip("")

    def _test_gemini_connection(self):
        self._start_ai(
            self.gemini_test_button,
            self.gemini.test_connection,
            (),
            self._gemini_test_succeeded,
            "Testing Gemini API authentication…",
            self._gemini_test_failed,
        )

    def _gemini_test_succeeded(self, _result):
        self._update_gemini_auth_ui("Gemini returned a valid response. Career guidance features are ready.")

    def _gemini_test_failed(self, _error):
        self._update_gemini_auth_ui("Gemini authentication could not be verified. Check the credential, network, and API access, then try again.")

    def _page_dashboard(self):
        page, layout = make_page()
        self.dashboard_layout = layout
        return page

    def _refresh_dashboard(self):
        clear_layout(self.dashboard_layout)
        profile = self.db.get_profile()
        data = self.db.analytics()
        hero_row = QHBoxLayout()
        hero = self._card(accent=True)
        hero.layout_box.addWidget(heading("YOUR CAREER PATH, MADE PRACTICAL", "eyebrow"))
        hero.layout_box.addWidget(heading(f"Welcome back, {profile.name.split()[0]}", "title"))
        hero.layout_box.addWidget(heading(f"You’re exploring {profile.career_goal} · {profile.experience} stage", "muted"))
        action_row = QHBoxLayout()
        action = make_button("Analyze My Career  →", primary=True)
        action.clicked.connect(lambda: (self.navigate("Career reality check"), self._start_career_analysis()))
        action_row.addWidget(action); action_row.addStretch(1)
        hero.layout_box.addLayout(action_row)
        hero_row.addWidget(hero, 3)
        side = self._card("This week", "One focused step at a time")
        side.layout_box.addWidget(heading("Your next move", "eyebrow"))
        open_items = [a for a in data["activities"] if a.status != "Completed"]
        side.layout_box.addWidget(heading(open_items[0].title if open_items else "Choose a new stretch goal"))
        roadmap = make_button("Open learning roadmap")
        roadmap.clicked.connect(lambda: self.navigate("Learning roadmap"))
        side.layout_box.addWidget(roadmap)
        hero_row.addWidget(side, 2)
        self.dashboard_layout.addLayout(hero_row)

        total = data["total"]
        progress = round(data["completed"] * 100 / total) if total else 0
        stats = QHBoxLayout()
        stats.addWidget(self._stat_card(f"{progress}%", "Roadmap progress", f"{data['completed']} of {total} activities completed"))
        stats.addWidget(self._stat_card(str(len(data["skills"])), "Skills in focus", "Self-reported · update any time"))
        stats.addWidget(self._stat_card(str(data["active_projects"]), "Active projects", f"{data['review_count']} saved portfolio reviews"))
        self.dashboard_layout.addLayout(stats)

        sections = QHBoxLayout()
        skills_card = self._card("Skills you’re developing", "Current self-assessment compared with your own targets")
        for skill in data["skills"][:4]:
            row = QHBoxLayout(); row.addWidget(heading(skill.name)); row.addStretch(1); row.addWidget(badge(skill.importance, "purple" if skill.importance == "Essential" else "gray")); skills_card.layout_box.addLayout(row)
            if skill.proficiency is None:
                skills_card.layout_box.addWidget(heading("Not rated yet", "muted"))
            else:
                skills_card.layout_box.addWidget(SkillProgress(skill.proficiency))
        skills_button = make_button("Update skill assessment")
        skills_button.clicked.connect(lambda: self.navigate("Skill gap"))
        skills_card.layout_box.addWidget(skills_button)
        sections.addWidget(skills_card, 1)
        activity_card = self._card("Recent activity", "Your saved workspace history")
        recent = self.db.get_recent_activity(5)
        for message, date in recent:
            row = QHBoxLayout()
            dot = badge("•", "blue"); dot.setFixedSize(18, 18)
            message_label = heading(message); message_label.setWordWrap(False); message_label.setMinimumWidth(170)
            date_label = heading(display_timestamp(date), "muted"); date_label.setMinimumWidth(112)
            row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter); row.addWidget(message_label, 1); row.addWidget(date_label)
            activity_card.layout_box.addLayout(row)
        if not recent: activity_card.layout_box.addWidget(heading("Activity will appear here as you work.", "muted"))
        sections.addWidget(activity_card, 1)
        self.dashboard_layout.addLayout(sections)
        self.dashboard_layout.addStretch(1)

    def _page_career(self):
        page, layout = make_page()
        layout.addWidget(heading("Career reality check", "title"))
        layout.addWidget(heading("Turn a job title into a practical, personalized starting point. Recommendations are learning guidance, not official requirements.", "muted"))
        card = self._card("What are you aiming for?", "Choose a suggested career or type any custom role. This career becomes the shared profile selection.")
        line = QHBoxLayout()
        profile = self.db.get_profile()
        self.career_goal_input = self._career_picker(profile.career_goal)
        self.career_goal_input.setToolTip("Search the career list or enter any custom career title.")
        line.addWidget(self.career_goal_input, 1)
        self.career_industry = self._industry_picker(profile.industry)
        line.addWidget(self.career_industry)
        self.career_button = make_button("Run reality check", primary=True)
        self.career_button.setMinimumWidth(132)
        self.career_button.clicked.connect(self._start_career_analysis)
        line.addWidget(self.career_button)
        card.layout_box.addLayout(line)
        layout.addWidget(card)
        self.career_result = QVBoxLayout(); self.career_result.setSpacing(14)
        layout.addLayout(self.career_result)
        layout.addStretch(1)
        return page

    def _start_career_analysis(self):
        goal = self.career_goal_input.currentText().strip() if hasattr(self, "career_goal_input") else self.db.get_profile().career_goal
        if not goal:
            self._notify("Add a career goal before analyzing.")
            return
        self._apply_career_selection(goal, self.career_industry.currentText() if hasattr(self, "career_industry") else "")
        profile = self.db.get_profile()
        skills = [s.__dict__ for s in self.db.get_skills()]
        self._start_ai(self.career_button if hasattr(self, "career_button") else None,
                       self.career_service.analyze, (self._profile_payload(profile), skills),
                       self._render_career_report, "Analyzing your career path…")

    def _render_career_report(self, report):
        self.career_report = report
        self._set_source_mode(report.get("source_mode", "LIVE GEMINI API"))
        profile = self.db.get_profile()
        self._save_recommendation(profile.career_goal, profile.industry, "career_reality_check", report, report.get("source_mode", "Unknown"))
        clear_layout(self.career_result)
        overview = self._card("A practical view", report.get("overview", ""), accent=True)
        overview.layout_box.addWidget(badge(report.get("source_mode", "LIVE GEMINI API"), "green"))
        self.career_result.addWidget(overview)
        row = QHBoxLayout()
        row.addWidget(self._bullet_group("Core skill areas", report.get("essential_skills", []), "blue"))
        row.addWidget(self._bullet_group("Optional skills", report.get("optional_skills", []), "purple"))
        row.addWidget(self._bullet_group("Your starting strengths", report.get("strengths", []), "green"))
        self.career_result.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(self._bullet_group("Development areas", report.get("growth_areas", []), "gold"))
        row2.addWidget(self._bullet_group("Next steps", report.get("next_steps", []), "blue"))
        self.career_result.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(self._bullet_group("Tools to explore", report.get("common_tools", []), "purple"))
        row3.addWidget(self._bullet_group("Portfolio or work evidence", report.get("portfolio_expectations", []), "green"))
        row3.addWidget(self._bullet_group("Learning routes", report.get("education_paths", []), "blue"))
        self.career_result.addLayout(row3)
        note = self._card("Source and confidence note")
        note.layout_box.addWidget(heading(report.get("sources_note", "Verify career requirements with current sources.")))
        self.career_result.addWidget(note)
        self._notify("Career reality check ready")

    def _page_skills(self):
        page, layout = make_page()
        layout.addWidget(heading("Skill gap analyzer", "title"))
        layout.addWidget(heading("Your ratings are self-reported snapshots, not objective measurements. Adjust them as your practice changes.", "muted"))
        intro_row = QHBoxLayout()
        info = self._card("How to read this", "Blue bars are your current self-assessment. Purple ticks are the development targets you chose.")
        info.layout_box.addWidget(badge("SELF-REPORTED", "gold"))
        intro_row.addWidget(info, 2)
        save_card = self._card("Keep your assessment current")
        self.skill_save_button = make_button("Save skill updates", primary=True)
        self.skill_save_button.clicked.connect(self._save_skills)
        save_card.layout_box.addWidget(heading("Rate only skills you have assessed. Leave either value unselected when unknown."))
        save_card.layout_box.addWidget(self.skill_save_button)
        self.skill_guidance_button = make_button("Generate skill guidance")
        self.skill_guidance_button.setMinimumWidth(150)
        self.skill_guidance_button.clicked.connect(self._start_skill_guidance)
        save_card.layout_box.addWidget(self.skill_guidance_button)
        intro_row.addWidget(save_card, 1)
        layout.addLayout(intro_row)
        self.skill_guidance_layout = QVBoxLayout(); self.skill_guidance_layout.setSpacing(10)
        layout.addLayout(self.skill_guidance_layout)
        self.skill_rows_layout = QVBoxLayout(); self.skill_rows_layout.setSpacing(9)
        add_row = QHBoxLayout()
        self.new_skill_input = QLineEdit(); self.new_skill_input.setPlaceholderText("Add a skill you already have or want to assess")
        add_skill_button = make_button("Add skill", quiet=True); add_skill_button.clicked.connect(self._add_student_skill)
        add_row.addWidget(self.new_skill_input, 1); add_row.addWidget(add_skill_button)
        layout.addLayout(add_row)
        layout.addLayout(self.skill_rows_layout)
        chart_card = self._card("Skills at a glance", "Self-reported proficiency and chosen target")
        self.skill_chart = ChartCanvas(height=3.2)
        chart_card.layout_box.addWidget(self.skill_chart)
        layout.addWidget(chart_card)
        layout.addStretch(1)
        self.skill_inputs = {}
        self._populate_skill_rows()
        return page

    def _populate_skill_rows(self):
        if not hasattr(self, "skill_rows_layout"): return
        clear_layout(self.skill_rows_layout)
        self.skill_inputs = {}
        for skill in self.db.get_skills():
            card = Card()
            row = QHBoxLayout(); row.setSpacing(12)
            name_box = QVBoxLayout(); name_box.addWidget(heading(skill.name)); name_box.addWidget(heading(skill.explanation, "muted"))
            if skill.exercise:
                name_box.addWidget(heading("Practice: " + skill.exercise, "muted"))
            row.addLayout(name_box, 2)
            row.addWidget(badge(skill.importance, "purple" if skill.importance == "Essential" else "gray"))
            current = QComboBox(); current.addItem("Now · not rated", None)
            target = QComboBox(); target.addItem("Target · not set", None)
            for value in range(0, 101, 5):
                current.addItem(f"Now · {value}/100", value); target.addItem(f"Target · {value}/100", value)
            if skill.proficiency is not None: current.setCurrentIndex(current.findData(skill.proficiency))
            if skill.target is not None: target.setCurrentIndex(target.findData(skill.target))
            row.addWidget(current); row.addWidget(target)
            card.layout_box.addLayout(row)
            self.skill_rows_layout.addWidget(card)
            self.skill_inputs[skill.name] = (current, target, skill)

    def _refresh_skill_chart(self):
        if hasattr(self, "skill_chart"):
            self.skill_chart.draw_skill_chart(self.db.get_skills())

    def _save_skills(self):
        for name, (current, target, skill) in self.skill_inputs.items():
            self.db.save_skill(name, current.currentData(), target.currentData(), skill.importance, skill.explanation, skill.exercise)
            career = self.db.get_profile().career_goal
            self._persist_remote_record("assessment", f"skill:{career}:{name}", {
                "career_goal":career, "skill":name, "proficiency":current.currentData(),
                "target":target.currentData(), "importance":skill.importance,
                "explanation":skill.explanation, "exercise":skill.exercise})
        self._refresh_skill_chart()
        self._notify("Skill assessments saved to this device")
        self._refresh_dashboard()

    def _add_student_skill(self):
        name = self.new_skill_input.text().strip()
        if not name: return
        if any(skill.name.casefold() == name.casefold() for skill in self.db.get_skills()):
            self._notify("That skill is already listed."); return
        self.db.save_skill(name)
        self.new_skill_input.clear()
        self._populate_skill_rows(); self._refresh_skill_chart(); self._refresh_dashboard()
        self._notify(f"Added {name}; rate it when ready")

    def _start_skill_guidance(self):
        self._save_skills()
        profile = self.db.get_profile()
        skills = [s.__dict__ for s in self.db.get_skills()]
        self._start_ai(self.skill_guidance_button, self.career_service.analyze_skills,
                       (self._profile_payload(profile), skills), self._render_skill_guidance,
                       "Generating practice guidance for your skills…")

    def _render_skill_guidance(self, report):
        self._set_source_mode(report.get("source_mode", "LIVE GEMINI API"))
        profile = self.db.get_profile()
        self._save_recommendation(profile.career_goal, profile.industry, "skill_gap_analysis", report, report.get("source_mode", "Unknown"))
        clear_layout(self.skill_guidance_layout)
        card = self._card(f"AI skill guidance · {profile.career_goal}", report.get("summary", ""), accent=True)
        card.layout_box.addWidget(badge(report.get("source_mode", "SKILL GUIDANCE"), "purple"))
        for item in report.get("skill_guidance", []):
            nested = Card()
            nested.layout_box.addWidget(heading(item.get("name", "Skill"), "heading"))
            nested.layout_box.addWidget(heading("Importance: " + item.get("importance", ""), "muted"))
            nested.layout_box.addWidget(heading("Your status: " + item.get("current_assessment", "Not rated"), "muted"))
            nested.layout_box.addWidget(heading("Development priority: " + item.get("development_priority", ""), "muted"))
            nested.layout_box.addWidget(heading(item.get("explanation", "")))
            nested.layout_box.addWidget(heading("Practice: " + item.get("exercise", ""), "muted"))
            card.layout_box.addWidget(nested)
        self.skill_guidance_layout.addWidget(card)
        self._notify("Gemini skill guidance saved")

    def _page_portfolio(self):
        page, layout = make_page()
        layout.addWidget(heading("Portfolio reviewer", "title"))
        layout.addWidget(heading("Get constructive feedback on an uploaded project image and the story behind your work.", "muted"))
        columns = QHBoxLayout()
        form_card = self._card("Tell us about the project", "PNG, JPG, or JPEG · one image per review")
        self.portfolio_name = QLineEdit(); self.portfolio_name.setPlaceholderText("Project name")
        self.portfolio_desc = QTextEdit(); self.portfolio_desc.setPlaceholderText("What did you make? What should a viewer notice?"); self.portfolio_desc.setFixedHeight(74)
        self.portfolio_category = QLineEdit(); self.portfolio_category.setPlaceholderText("Selected profile career"); self.portfolio_category.setReadOnly(True)
        self.portfolio_category.setText(self.db.get_profile().career_goal)
        self.portfolio_software = QLineEdit(); self.portfolio_software.setPlaceholderText("Software used")
        self.portfolio_skills = QLineEdit(); self.portfolio_skills.setPlaceholderText("Skills demonstrated, separated by commas")
        self.portfolio_goal = QLineEdit(); self.portfolio_goal.setPlaceholderText("What did you want to achieve?")
        for label_text, widget in [("Project name",self.portfolio_name),("Description",self.portfolio_desc),("Career category",self.portfolio_category),("Software",self.portfolio_software),("Skills",self.portfolio_skills),("Intended outcome",self.portfolio_goal)]:
            form_card.layout_box.addWidget(heading(label_text, "eyebrow")); form_card.layout_box.addWidget(widget)
        upload_row = QHBoxLayout()
        self.upload_button = make_button("Choose project image")
        self.upload_button.clicked.connect(self._choose_image)
        upload_row.addWidget(self.upload_button)
        self.image_label = QLabel("No image selected")
        self.image_label.setObjectName("muted")
        upload_row.addWidget(self.image_label, 1)
        form_card.layout_box.addLayout(upload_row)
        self.portfolio_review_button = make_button("Review my project", primary=True)
        self.portfolio_review_button.setMinimumWidth(140)
        self.portfolio_review_button.clicked.connect(self._start_portfolio_review)
        form_card.layout_box.addWidget(self.portfolio_review_button)
        columns.addWidget(form_card, 3)
        preview = self._card("Image preview", "The image is sent only when you run a Gemini image review.")
        self.preview_label = QLabel("Your selected image will appear here")
        self.preview_label.setMinimumSize(260, 230)
        self.preview_label.setMaximumHeight(300)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#101725;border:1px dashed #344259;border-radius:9px;color:#8090a8;")
        preview.layout_box.addWidget(self.preview_label)
        preview.layout_box.addWidget(heading("AI feedback is coaching, not an objective quality score or readiness verdict.", "muted"))
        columns.addWidget(preview, 2)
        layout.addLayout(columns)
        self.portfolio_report_layout = QVBoxLayout(); self.portfolio_report_layout.setSpacing(12)
        layout.addLayout(self.portfolio_report_layout)
        history_card = self._card("Previous reviews", "Your saved evaluation reports")
        self.review_history_layout = QVBoxLayout(); history_card.layout_box.addLayout(self.review_history_layout)
        layout.addWidget(history_card)
        layout.addStretch(1)
        return page

    def _choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a portfolio image", "", "Images (*.png *.jpg *.jpeg)")
        if not path: return
        try:
            info = self.portfolio_service.inspect_image(path)
            ext = Path(path).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg"}: raise ValueError("Please choose a PNG, JPG, or JPEG image.")
        except Exception as exc:
            QMessageBox.warning(self, "Image could not be opened", str(exc)); return
        self.current_image = path
        self.image_label.setText(f"{Path(path).name} · {info['width']}×{info['height']}")
        pixmap = QPixmap(path)
        self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _start_portfolio_review(self):
        if not self.current_image:
            QMessageBox.information(self, "Choose an image", "Select a PNG, JPG, or JPEG project image first."); return
        name = self.portfolio_name.text().strip() or "Untitled portfolio project"
        profile = self.db.get_profile()
        details = {"profile":self._profile_payload(profile),"name":name,"description":self.portfolio_desc.toPlainText().strip(),"category":profile.career_goal,"industry":profile.industry,
                   "software":self.portfolio_software.text().strip(),"skills":[x.strip() for x in self.portfolio_skills.text().split(",") if x.strip()],"goal":self.portfolio_goal.text().strip()}
        self._start_ai(self.portfolio_review_button, self.portfolio_service.review, (self.current_image, details),
                       partial(self._save_and_render_review, name, self.current_image), "Reviewing your project image…")

    def _save_and_render_review(self, name, path, report):
        review_id = self.db.add_review(name, path, report, career_goal=self.db.get_profile().career_goal)
        self._persist_remote_record("portfolio", str(review_id), {"project_name":name,
            "career_goal":self.db.get_profile().career_goal, "report":report})
        clear_layout(self.portfolio_report_layout)
        self.portfolio_report_layout.addWidget(heading("YOUR EVALUATION", "eyebrow"))
        first = QHBoxLayout()
        groups = [("Presentation", report.get("presentation",[])),("What the image shows",report.get("technical_observations",[])),("Observed strengths",report.get("observed_strengths",[]))]
        for title, values in groups: first.addWidget(self._bullet_group(title, values))
        self.portfolio_report_layout.addLayout(first)
        second = QHBoxLayout()
        second.addWidget(self._bullet_group("Ways to improve", report.get("improvements",[]), "gold"))
        second.addWidget(self._bullet_group("Skills demonstrated", report.get("skills_demonstrated",[]), "green"))
        second.addWidget(self._bullet_group("Missing project information", report.get("missing_information",[]), "blue"))
        second.addWidget(self._bullet_group("Recommended next steps", report.get("recommended_next_steps",[]), "purple"))
        self.portfolio_report_layout.addLayout(second)
        follow = self._card("Recommended next project", report.get("next_project", ""), accent=True)
        follow.layout_box.addWidget(heading("Portfolio presentation"));
        for tip in report.get("portfolio_tips",[]): follow.layout_box.addWidget(heading(f"•  {tip}"))
        follow.layout_box.addWidget(badge(report.get("source_mode", "SAVED REVIEW"), "purple"))
        self.portfolio_report_layout.addWidget(follow)
        limitation = self._card("Feedback limitations")
        limitation.layout_box.addWidget(heading(report.get("limitations", "Use this as reflective coaching; a single image cannot establish readiness.")))
        self.portfolio_report_layout.addWidget(limitation)
        self._refresh_review_history()
        self._refresh_analytics()
        self._notify("Portfolio review saved")

    def _refresh_review_history(self):
        if not hasattr(self, "review_history_layout"): return
        clear_layout(self.review_history_layout)
        reviews = self.db.get_reviews()
        if not reviews:
            self.review_history_layout.addWidget(heading("Your saved reviews will appear here.", "muted")); return
        for review in reviews[:6]:
            row = QHBoxLayout(); row.addWidget(badge("GEMINI REVIEW", "green")); row.addWidget(heading(review.project_name)); row.addStretch(1); row.addWidget(heading(display_timestamp(review.created_at), "muted"))
            self.review_history_layout.addLayout(row)

    def _page_roadmap(self):
        page, layout = make_page()
        layout.addWidget(heading("Adaptive learning roadmap", "title"))
        layout.addWidget(heading("Move through three stages at your pace. Suggestions wait for your approval and never remove progress.", "muted"))
        intro = QHBoxLayout()
        summary = self._card("A roadmap that learns with you", "Complete an activity, update your skill profile, or save new portfolio feedback. Then ask for a fresh suggestion.")
        self.adapt_button = make_button("Suggest roadmap updates", primary=True)
        self.adapt_button.setMinimumWidth(180)
        self.adapt_button.clicked.connect(self._start_roadmap_suggestions)
        summary.layout_box.addWidget(self.adapt_button)
        self.roadmap_generate_button = make_button("Generate career roadmap", quiet=True)
        self.roadmap_generate_button.clicked.connect(self._start_roadmap_generation)
        summary.layout_box.addWidget(self.roadmap_generate_button)
        intro.addWidget(summary, 3)
        self.roadmap_overall_card = self._card("Current progress")
        self.roadmap_progress_label = QLabel("0%")
        self.roadmap_progress_label.setObjectName("statValue")
        self.roadmap_overall_card.layout_box.addWidget(self.roadmap_progress_label)
        self.roadmap_bar = roadmap_progress(0)
        self.roadmap_overall_card.layout_box.addWidget(self.roadmap_bar)
        intro.addWidget(self.roadmap_overall_card, 1)
        layout.addLayout(intro)
        self.roadmap_stage_layout = QVBoxLayout(); self.roadmap_stage_layout.setSpacing(13)
        layout.addLayout(self.roadmap_stage_layout)
        layout.addStretch(1)
        return page

    def _refresh_roadmap(self):
        if not hasattr(self, "roadmap_stage_layout"): return
        clear_layout(self.roadmap_stage_layout)
        activities = self.db.get_activities()
        if hasattr(self, "roadmap_generate_button"):
            self.roadmap_generate_button.setVisible(True)
            self.roadmap_generate_button.setText(("Regenerate " if activities else "Generate ") + f"{self.db.get_profile().career_goal} roadmap")
        complete = sum(a.status == "Completed" for a in activities)
        value = round(complete * 100 / len(activities)) if activities else 0
        self.roadmap_progress_label.setText(f"{value}%")
        self.roadmap_bar.setValue(value); self.roadmap_bar.setFormat(f"{complete} of {len(activities)} activities complete")
        for stage in ["Beginner", "Intermediate", "Advanced"]:
            group = [a for a in activities if a.stage == stage]
            stage_card = self._card(stage, f"{sum(a.status == 'Completed' for a in group)} of {len(group)} completed · {stage.lower()} stage")
            if not group:
                stage_card.layout_box.addWidget(heading("No activities yet.", "muted"))
            for activity in group:
                nested = Card()
                top = QHBoxLayout(); top.addWidget(heading(activity.title)); top.addStretch(1)
                top.addWidget(badge(activity.status.upper(), "green" if activity.status == "Completed" else "blue"))
                nested.layout_box.addLayout(top)
                nested.layout_box.addWidget(heading(activity.description))
                if activity.learning_objective:
                    nested.layout_box.addWidget(heading("Learning objective: " + activity.learning_objective, "muted"))
                meta = QHBoxLayout(); meta.addWidget(badge(activity.difficulty, "purple")); meta.addWidget(badge(activity.duration, "gray")); meta.addWidget(heading("Skills: " + ", ".join(activity.skills), "muted")); meta.addStretch(1)
                nested.layout_box.addLayout(meta)
                nested.layout_box.addWidget(heading("Outcome: " + activity.outcome, "muted"))
                if activity.rationale: nested.layout_box.addWidget(heading("Why this is here: " + activity.rationale, "muted"))
                if activity.notes:
                    nested.layout_box.addWidget(heading("Your notes: " + activity.notes, "muted"))
                controls = QHBoxLayout()
                status = QComboBox(); status.addItems(["Planned", "In progress", "Paused", "Completed"])
                status.setCurrentText(activity.status); status.currentTextChanged.connect(partial(self._set_activity_status, activity.id))
                edit = make_button("Edit details", quiet=True); edit.clicked.connect(partial(self._edit_activity, activity))
                notes = make_button("Edit notes", quiet=True); notes.clicked.connect(partial(self._edit_activity_notes, activity))
                up = make_button("Move up", quiet=True); up.clicked.connect(partial(self._move_activity, activity.id, -1))
                down = make_button("Move down", quiet=True); down.clicked.connect(partial(self._move_activity, activity.id, 1))
                controls.addWidget(status); controls.addWidget(edit); controls.addWidget(notes)
                controls.addWidget(up); controls.addWidget(down); controls.addStretch(1)
                nested.layout_box.addLayout(controls)
                stage_card.layout_box.addWidget(nested)
            self.roadmap_stage_layout.addWidget(stage_card)

    def _set_activity_status(self, activity_id, status):
        self.db.update_activity_status(activity_id, status)
        self._sync_activity(activity_id)
        self._refresh_roadmap(); self._refresh_dashboard(); self._refresh_analytics()
        self._notify(f"Activity marked {status.lower()}")

    def _edit_activity(self, activity):
        dialog = QDialog(self); dialog.setWindowTitle("Edit roadmap activity"); dialog.resize(600, 500)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        title = QLineEdit(activity.title); description = QTextEdit(); description.setPlainText(activity.description)
        objective = QLineEdit(activity.learning_objective); duration = QLineEdit(activity.duration)
        outcome = QTextEdit(); outcome.setPlainText(activity.outcome)
        form.addRow("Title", title); form.addRow("Description", description); form.addRow("Learning objective", objective)
        form.addRow("Duration", duration); form.addRow("Completion criteria", outcome); layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.update_activity(activity.id, title=title.text(), description=description.toPlainText(),
                    learning_objective=objective.text(), duration=duration.text(), outcome=outcome.toPlainText())
                self._sync_activity(activity.id)
                self._refresh_roadmap()
            except ValueError as exc:
                QMessageBox.warning(self, "Activity needs attention", str(exc))

    def _edit_activity_notes(self, activity):
        notes, accepted = QInputDialog.getMultiLineText(self, "Roadmap notes", "Your private note for this activity:", activity.notes)
        if accepted:
            self.db.update_activity_notes(activity.id, notes)
            self._sync_activity(activity.id)
            self._refresh_roadmap()

    def _move_activity(self, activity_id, direction):
        self.db.move_activity(activity_id, direction)
        for activity in self.db.get_activities():
            self._sync_activity(activity.id)
        self._refresh_roadmap()

    def _sync_activity(self, activity_id):
        activity = next((item for item in self.db.get_activities() if item.id == activity_id), None)
        if activity:
            self._persist_remote_record("activity", str(activity_id), activity.__dict__)

    def _start_roadmap_suggestions(self):
        profile = self.db.get_profile()
        skills = [s.__dict__ for s in self.db.get_skills()]
        activities = [a.__dict__ for a in self.db.get_activities()]
        reviews = [r.__dict__ for r in self.db.get_reviews()]
        self._start_ai(self.adapt_button, self.roadmap_service.suggest,
                       (profile, skills, activities, reviews, self._latest_recommendation("career_reality_check"), self._latest_recommendation("skill_gap_analysis")), self._approve_roadmap_suggestions,
                       "Finding a next step that fits your progress…")

    def _start_roadmap_generation(self):
        activities = [a.__dict__ for a in self.db.get_activities()]
        if activities:
            result = QMessageBox.question(self, "Replace current roadmap?",
                "The new Gemini roadmap will replace the current activities and their completion states after it is generated. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if result != QMessageBox.StandardButton.Yes:
                return
        self._pending_roadmap_replace = bool(activities)
        profile = self.db.get_profile()
        skills = [s.__dict__ for s in self.db.get_skills()]
        career_analysis = self._latest_recommendation("career_reality_check")
        skill_gap = self._latest_recommendation("skill_gap_analysis")
        self._start_ai(self.roadmap_generate_button, self.roadmap_service.generate,
                       (profile, skills, career_analysis, skill_gap, activities), self._save_generated_roadmap,
                       f"Building a {profile.career_goal} learning roadmap…")

    def _save_generated_roadmap(self, activities):
        profile = self.db.get_profile()
        if getattr(self, "_pending_roadmap_replace", False):
            self.db.clear_activities(profile.career_goal)
        self._pending_roadmap_replace = False
        source_mode = "LIVE GEMINI API"
        self._set_source_mode(source_mode)
        self._save_recommendation(profile.career_goal, profile.industry, "learning_roadmap", activities,
                                   source_mode)
        for item in activities:
            item["career_goal"] = profile.career_goal
            activity_id = self.db.add_activity(item)
            self._sync_activity(activity_id)
        self._refresh_roadmap(); self._refresh_dashboard(); self._refresh_analytics()
        self._notify(f"{profile.career_goal} roadmap saved")

    def _approve_roadmap_suggestions(self, suggestions):
        if not suggestions:
            self._notify("No roadmap changes suggested."); return
        profile = self.db.get_profile()
        for item in suggestions:
            item["career_goal"] = profile.career_goal
        source_mode = "LIVE GEMINI API"
        self._set_source_mode(source_mode)
        self._save_recommendation(profile.career_goal, profile.industry, "roadmap_suggestions", suggestions, source_mode)
        dialog = QDialog(self)
        dialog.setWindowTitle("Review roadmap suggestions")
        dialog.resize(600, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(heading("Review suggested additions", "title"))
        layout.addWidget(badge(source_mode, "green"))
        layout.addWidget(heading("Select activities to add. Existing completed and planned items will remain untouched.", "muted"))
        checks = []
        for item in suggestions:
            check = QCheckBox(f"{item.get('title','New activity')} · {item.get('stage','Intermediate')}")
            check.setChecked(True)
            check.setToolTip(item.get("rationale", ""))
            layout.addWidget(check)
            layout.addWidget(heading(item.get("rationale", ""), "muted"))
            layout.addWidget(heading(item.get("description", "")))
            checks.append((check,item))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add selected activities")
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = [item for check,item in checks if check.isChecked()]
            for item in selected: self.db.add_activity(item)
            self._refresh_roadmap(); self._refresh_dashboard()
            self._notify(f"Added {len(selected)} approved roadmap suggestion(s)")

    def _page_projects(self):
        page, layout = make_page()
        layout.addWidget(heading("Project studio", "title"))
        layout.addWidget(heading("Generate portfolio briefs shaped around your goal and the skills you want to practice.", "muted"))
        top = QHBoxLayout()
        generate_card = self._card("Create your next portfolio brief", "Ideas are stored only when you choose to save one.", accent=True)
        generate_card.layout_box.addWidget(heading("The generator looks at your career goal, self-reported skills, and recent feedback.", "muted"))
        self.project_generate_button = make_button("Generate project ideas", primary=True)
        self.project_generate_button.setMinimumWidth(155)
        self.project_generate_button.clicked.connect(self._start_project_generation)
        generate_card.layout_box.addWidget(self.project_generate_button)
        top.addWidget(generate_card, 2)
        active_card = self._card("Build a project with a clear outcome")
        active_card.layout_box.addWidget(heading("Save a brief to your project list, then capture the work in Portfolio Review."))
        portfolio_button = make_button("Open portfolio reviewer")
        portfolio_button.clicked.connect(lambda: self.navigate("Portfolio review"))
        active_card.layout_box.addWidget(portfolio_button)
        top.addWidget(active_card, 1)
        layout.addLayout(top)
        self.generated_layout = QVBoxLayout(); self.generated_layout.setSpacing(12)
        layout.addLayout(self.generated_layout)
        self.saved_projects_layout = QVBoxLayout(); self.saved_projects_layout.setSpacing(8)
        saved = self._card("My project list", "Saved briefs")
        saved.layout_box.addLayout(self.saved_projects_layout)
        layout.addWidget(saved)
        layout.addStretch(1)
        return page

    def _start_project_generation(self):
        profile = self.db.get_profile()
        skills = [s.__dict__ for s in self.db.get_skills()]
        reviews = [r.__dict__ for r in self.db.get_reviews()]
        completed = [p.__dict__ for p in self.db.get_projects() if p.status == "Completed"]
        self._start_ai(self.project_generate_button, self.career_service.generate_projects,
                       (self._profile_payload(profile), skills, completed, reviews), self._render_generated_projects,
                       "Creating project briefs…")

    def _render_generated_projects(self, projects):
        self.generated_projects = projects
        source_mode = "LIVE GEMINI API"
        self._set_source_mode(source_mode)
        profile = self.db.get_profile()
        self._save_recommendation(profile.career_goal, profile.industry, "project_ideas", projects,
                                   source_mode)
        clear_layout(self.generated_layout)
        for index, item in enumerate(projects):
            card = self._card(item.get("title", "Portfolio project"), item.get("concept", ""), accent=True)
            item_source = item.get("source_mode", source_mode)
            card.layout_box.addWidget(badge(item_source, "green"))
            card.layout_box.addWidget(badge(f"{item.get('difficulty','Intermediate')} · {item.get('duration','')}", "purple"))
            card.layout_box.addWidget(heading(item.get("description", "")))
            card.layout_box.addWidget(heading("Problem to explore: " + item.get("problem", ""), "muted"))
            card.layout_box.addWidget(heading("Skills: " + ", ".join(item.get("skills",[])), "muted"))
            if item.get("learning_objectives"):
                card.layout_box.addWidget(heading("Learning objectives: " + "; ".join(item["learning_objectives"]), "muted"))
            if item.get("materials"):
                card.layout_box.addWidget(heading("Materials: " + "; ".join(item["materials"]), "muted"))
            if item.get("stages"):
                card.layout_box.addWidget(heading("Development stages: " + " → ".join(item["stages"]), "muted"))
            card.layout_box.addWidget(heading("Recommended software: " + item.get("software", ""), "muted"))
            card.layout_box.addWidget(heading("Expected deliverable: " + item.get("deliverable", "")))
            card.layout_box.addWidget(heading("Portfolio value: " + item.get("portfolio_value", ""), "muted"))
            view = make_button("View full brief", quiet=True)
            view.clicked.connect(partial(self._show_project_detail, item))
            card.layout_box.addWidget(view, 0, Qt.AlignmentFlag.AlignRight)
            save = make_button("Save to my projects", primary=True)
            save.clicked.connect(partial(self._save_project, index))
            card.layout_box.addWidget(save, 0, Qt.AlignmentFlag.AlignRight)
            self.generated_layout.addWidget(card)
        self._notify("Project ideas ready · choose which to save")

    def _save_project(self, index):
        if index >= len(self.generated_projects): return
        item = self.generated_projects[index]
        project_id = self.db.add_project({"title":item["title"],"description":item["description"],"category":self.db.get_profile().career_goal,
                             "software":item.get("software",""),"skills":item.get("skills",[]),"details":item})
        self._persist_remote_record("project", str(project_id), {**item, "status":"Saved", "career_goal":self.db.get_profile().career_goal})
        self._refresh_saved_projects(); self._refresh_dashboard()
        self._notify(f"Saved project · {item['title']}")

    def _refresh_saved_projects(self):
        if not hasattr(self, "saved_projects_layout"): return
        clear_layout(self.saved_projects_layout)
        projects = self.db.get_projects()
        if not projects:
            self.saved_projects_layout.addWidget(heading("Saved project ideas will appear here.", "muted")); return
        for item in projects:
            row = QHBoxLayout(); row.addWidget(badge(item.status.upper(), "green" if item.status == "Completed" else "blue")); row.addWidget(heading(item.title)); row.addStretch(1)
            view = make_button("View brief", quiet=True); view.clicked.connect(partial(self._show_saved_project_detail, item)); row.addWidget(view)
            next_status = "In progress" if item.status == "Completed" else "Completed"
            action = make_button("Reopen" if item.status == "Completed" else "Mark complete")
            action.clicked.connect(partial(self._update_project_status, item.id, next_status)); row.addWidget(action)
            self.saved_projects_layout.addLayout(row)
            self.saved_projects_layout.addWidget(heading(item.description, "muted"))

    def _show_project_detail(self, item):
        dialog = QDialog(self); dialog.setWindowTitle(item.get("title", "Project brief")); dialog.resize(640, 570)
        layout = QVBoxLayout(dialog)
        layout.addWidget(heading(item.get("title", "Portfolio project"), "title"))
        layout.addWidget(badge(f"{item.get('difficulty','')} · {item.get('duration','')}", "purple"))
        for label, text in [("Concept",item.get("concept","")),("Description",item.get("description","")),("Problem to explore",item.get("problem","")),
                            ("Required skills",", ".join(item.get("skills",[]))),
                            ("Learning objectives", "; ".join(item.get("learning_objectives", []))),
                            ("Materials", "; ".join(item.get("materials", []))),
                            ("Development stages", " → ".join(item.get("stages", []))),
                            ("Recommended software",item.get("software","")),
                            ("Expected deliverable",item.get("deliverable","")), ("Portfolio value",item.get("portfolio_value",""))]:
            if text:
                layout.addWidget(heading(label.upper(), "eyebrow")); layout.addWidget(heading(text))
        close = make_button("Close", quiet=True); close.clicked.connect(dialog.accept); layout.addWidget(close,0,Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _show_saved_project_detail(self, project):
        detail = dict(project.details)
        detail.setdefault("title", project.title); detail.setdefault("description", project.description)
        detail.setdefault("software", project.software); detail.setdefault("skills", project.skills)
        self._show_project_detail(detail)

    def _update_project_status(self, project_id, status):
        self.db.update_project_status(project_id, status)
        project = next((item for item in self.db.get_projects() if item.id == project_id), None)
        if project:
            self._persist_remote_record("project", str(project_id), project.__dict__)
        self._refresh_saved_projects(); self._refresh_dashboard(); self._refresh_analytics()
        self._notify(f"Project marked {status.lower()}")

    def _page_explorer(self):
        page, layout = make_page()
        layout.addWidget(heading("Career explorer", "title"))
        layout.addWidget(heading("Search the career catalog or enter any custom role. The first path is saved as your shared profile career.", "muted"))
        profile = self.db.get_profile()
        choose = self._card("Choose two paths", "Compare responsibilities and learning considerations for two student-selected careers.")
        row = QHBoxLayout()
        self.career_a = self._career_picker(profile.career_goal)
        self.career_a_industry = self._industry_picker(profile.industry)
        self.career_b = self._career_picker("")
        self.career_b.setPlaceholderText("Search or enter another career")
        self.career_b_industry = self._industry_picker("Other / custom")
        self.compare_button = make_button("Compare careers", primary=True)
        self.compare_button.setMinimumWidth(135)
        self.compare_button.clicked.connect(self._start_career_compare)
        row.addWidget(self.career_a,2); row.addWidget(self.career_a_industry,1)
        row.addWidget(self.career_b,2); row.addWidget(self.career_b_industry,1); row.addWidget(self.compare_button)
        choose.layout_box.addLayout(row); layout.addWidget(choose)
        self.compare_result_layout = QVBoxLayout(); layout.addLayout(self.compare_result_layout)
        layout.addStretch(1)
        return page

    def _start_career_compare(self):
        a, b = self.career_a.currentText().strip(), self.career_b.currentText().strip()
        if not a or not b: self._notify("Enter two career paths to compare."); return
        self._apply_career_selection(a, self.career_a_industry.currentText())
        profile = self.db.get_profile()
        industry_b = infer_industry(b, self.career_b_industry.currentText())
        self._start_ai(self.compare_button, self.career_service.compare_careers,
                       (profile.career_goal,b,profile.industry,industry_b), self._render_career_compare, "Comparing career paths…")

    def _render_career_compare(self, result):
        self._set_source_mode(result.get("mode", "LIVE GEMINI API"))
        profile = self.db.get_profile()
        self._save_recommendation(profile.career_goal, profile.industry, "career_comparison", result,
                                   result.get("mode", "GEMINI RESPONSE"))
        clear_layout(self.compare_result_layout)
        row = QHBoxLayout()
        for key in ["career_a","career_b"]:
            career = result.get(key,{})
            card = self._card(career.get("career", "Career path"), career.get("overview", ""), accent=True)
            if career.get("responsibilities"):
                card.layout_box.addWidget(heading("Common responsibilities", "eyebrow"))
                for item in career["responsibilities"]: card.layout_box.addWidget(heading(f"•  {item}"))
            card.layout_box.addWidget(heading("Relevant skills", "eyebrow"))
            for item in career.get("skills",[]): card.layout_box.addWidget(heading(f"•  {item}"))
            card.layout_box.addWidget(heading("Tools you may encounter", "eyebrow"))
            for item in career.get("tools",[]): card.layout_box.addWidget(heading(f"•  {item}"))
            card.layout_box.addWidget(heading("Portfolio examples", "eyebrow")); card.layout_box.addWidget(heading(career.get("portfolio", "")))
            if career.get("related"):
                card.layout_box.addWidget(heading("Related paths: " + ", ".join(career["related"]), "muted"))
            row.addWidget(card)
        self.compare_result_layout.addLayout(row)
        note = self._card("How to use this comparison")
        note.layout_box.addWidget(heading(result.get("mode", "General career guidance. Verify details with current sources.")))
        self.compare_result_layout.addWidget(note)
        self._notify("Career comparison ready")

    def _page_opportunities(self):
        page, layout = make_page()
        layout.addWidget(heading("Opportunities & Colleges", "title"))
        layout.addWidget(heading("Search live web results for programs, internships, events, competitions, and research. Dates and eligibility remain unverified until you check the linked source.", "muted"))
        search = self._card("Find opportunities", "Results come from a live search provider configured by the service owner.")
        form = QFormLayout(); form.setSpacing(10)
        self.opportunity_query = QLineEdit(); self.opportunity_query.setPlaceholderText("For example, summer engineering programs")
        self.opportunity_career = QLineEdit(self.db.get_profile().career_goal if self.db.has_profile() else "")
        self.opportunity_category = QComboBox(); self.opportunity_category.addItem("Any opportunity", "other")
        for label, value in [("College / university", "college"), ("Event / competition", "event"),
                             ("Internship", "internship"), ("Summer program", "summer_program"), ("Research", "research")]:
            self.opportunity_category.addItem(label, value)
        self.opportunity_location = QLineEdit(); self.opportunity_location.setPlaceholderText("City, region, or country (optional)")
        self.opportunity_education = QLineEdit(self.db.get_profile().education_level if self.db.has_profile() else "")
        form.addRow("Search", self.opportunity_query); form.addRow("Career", self.opportunity_career)
        form.addRow("Category", self.opportunity_category); form.addRow("Location", self.opportunity_location)
        form.addRow("Education level", self.opportunity_education)
        search.layout_box.addLayout(form)
        self.opportunity_search_button = make_button("Search live results", primary=True)
        self.opportunity_search_button._prior_text = "Search live results"
        self.opportunity_search_button.clicked.connect(self._search_opportunities)
        search.layout_box.addWidget(self.opportunity_search_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(search)
        self.opportunity_results = QVBoxLayout(); self.opportunity_results.setSpacing(12)
        layout.addLayout(self.opportunity_results)
        saved = self._card("Saved opportunities", "Track opportunities you want to follow.")
        self.saved_opportunities_layout = QVBoxLayout(); self.saved_opportunities_layout.setSpacing(10)
        saved.layout_box.addLayout(self.saved_opportunities_layout)
        layout.addWidget(saved)
        layout.addStretch(1)
        return page

    def _run_service_operation(self, button, operation, args, kwargs, callback, label):
        if not self.api_client.authenticated:
            self.navigate("Service & account")
            return
        prior = getattr(button, "_prior_text", button.text())
        button._prior_text = prior
        button.setEnabled(False); button.setText("Working…")
        self._notify(label)
        worker = AIWorker(operation, *args, **kwargs)
        self._workers.add(worker)
        def success(result):
            button.setEnabled(True); button.setText(prior)
            callback(result)
        def failure(error):
            button.setEnabled(True); button.setText(prior)
            QMessageBox.warning(self, "SkillBridge service request failed", error)
            self._notify("Service request failed")
        worker.succeeded.connect(success); worker.failed.connect(failure)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        worker.start()

    def _search_opportunities(self):
        query = self.opportunity_query.text().strip()
        if len(query) < 2:
            QMessageBox.information(self, "Add a search term", "Enter at least two characters to search.")
            return
        filters = {"query": query, "career": self.opportunity_career.text().strip(),
                   "category": self.opportunity_category.currentData(),
                   "location": self.opportunity_location.text().strip(),
                   "education_level": self.opportunity_education.text().strip(), "limit": 10}
        self._run_service_operation(self.opportunity_search_button, self.api_client.search_opportunities,
                                    (), filters, self._render_opportunity_results, "Searching live opportunity sources…")

    def _render_opportunity_results(self, response):
        clear_layout(self.opportunity_results)
        results = response.get("results", [])
        if not results:
            self.opportunity_results.addWidget(heading("No live results were returned. Try different search terms.", "muted"))
            return
        for item in results:
            card = self._card(item.get("title", "Opportunity"), item.get("source_name", "Live search result"), accent=True)
            card.layout_box.addWidget(heading(item.get("snippet", "No summary was supplied by the source.")))
            card.layout_box.addWidget(heading(f"Location: {item.get('location', 'Not listed')} · Deadline: {item.get('deadline', 'Not verified')}", "muted"))
            card.layout_box.addWidget(heading(item.get("verification", "Details are not independently verified; check the source."), "muted"))
            row = QHBoxLayout()
            open_button = make_button("Open source", quiet=True)
            open_button.clicked.connect(lambda _checked=False, url=item.get("source_url", ""): QDesktopServices.openUrl(QUrl(url)))
            save_button = make_button("Save opportunity", primary=True)
            save_button.clicked.connect(lambda _checked=False, opportunity=item, button=save_button: self._save_opportunity(opportunity, button))
            row.addWidget(open_button); row.addWidget(save_button); row.addStretch(1)
            card.layout_box.addLayout(row)
            self.opportunity_results.addWidget(card)

    def _save_opportunity(self, item, button):
        button.setEnabled(False)
        try:
            self.api_client.save_opportunity(item)
            self._load_saved_opportunities()
            self._notify("Opportunity saved to your account")
        except ApiError as exc:
            button.setEnabled(True)
            QMessageBox.warning(self, "Could not save opportunity", str(exc))

    def _load_saved_opportunities(self):
        if not hasattr(self, "saved_opportunities_layout") or not self.api_client.authenticated:
            return
        self._run_service_operation(None if False else self.opportunity_search_button,
                                    self.api_client.saved_opportunities, (), {},
                                    self._render_saved_opportunities, "Loading your saved opportunities…")

    def _render_saved_opportunities(self, results):
        clear_layout(self.saved_opportunities_layout)
        if not results:
            self.saved_opportunities_layout.addWidget(heading("You have not saved any opportunities yet.", "muted"))
            return
        for item in results:
            row = QHBoxLayout()
            row.addWidget(badge(item.get("application_status", "Saved"), "blue"))
            row.addWidget(heading(item.get("title", "Opportunity")))
            row.addWidget(heading(item.get("deadline") or "Deadline not verified", "muted"))
            open_button = make_button("Open source", quiet=True)
            open_button.clicked.connect(lambda _checked=False, url=item.get("source_url", ""): QDesktopServices.openUrl(QUrl(url)))
            row.addWidget(open_button)
            status = QComboBox(); status.addItems(["Saved", "Considering", "Applied", "Not pursuing"])
            status.setCurrentText(item.get("application_status", "Saved"))
            status.currentTextChanged.connect(lambda value, oid=item["id"]: self._update_opportunity_status(oid, value))
            row.addWidget(status)
            remove = make_button("Remove", quiet=True)
            remove.clicked.connect(lambda _checked=False, oid=item["id"]: self._delete_opportunity(oid))
            row.addWidget(remove); row.addStretch(1)
            self.saved_opportunities_layout.addLayout(row)
            self.saved_opportunities_layout.addWidget(heading(item.get("source_name", "Source") + " · Information not independently verified", "muted"))

    def _update_opportunity_status(self, opportunity_id, value):
        try:
            self.api_client.update_saved_opportunity(opportunity_id, value)
        except ApiError as exc:
            QMessageBox.warning(self, "Could not update application status", str(exc))

    def _delete_opportunity(self, opportunity_id):
        try:
            self.api_client.delete_saved_opportunity(opportunity_id)
            self._load_saved_opportunities()
        except ApiError as exc:
            QMessageBox.warning(self, "Could not remove opportunity", str(exc))

    def _page_analytics(self):
        page, layout = make_page()
        layout.addWidget(heading("Progress analytics", "title"))
        layout.addWidget(heading("Charts are built from your saved local assessments, activities, projects, and reviews.", "muted"))
        self.analytics_stats = QHBoxLayout(); layout.addLayout(self.analytics_stats)
        row = QHBoxLayout()
        skill_card = self._card("Skill development", "Current self-reported levels compared with personal targets")
        self.analytics_skill_chart = ChartCanvas(height=3.2); skill_card.layout_box.addWidget(self.analytics_skill_chart)
        roadmap_card = self._card("Learning activity", "Completed and planned activities across the three stages")
        self.analytics_progress_chart = ChartCanvas(height=3.2); roadmap_card.layout_box.addWidget(self.analytics_progress_chart)
        row.addWidget(skill_card,1); row.addWidget(roadmap_card,1); layout.addLayout(row)
        detail_card = self._card("Portfolio and projects")
        self.analytics_detail = QVBoxLayout(); self.analytics_detail.setSpacing(14); detail_card.layout_box.addLayout(self.analytics_detail)
        detail_card.setMinimumHeight(160)
        layout.addWidget(detail_card)
        layout.addStretch(1)
        return page

    def _refresh_analytics(self):
        if not hasattr(self, "analytics_skill_chart"): return
        data = self.db.analytics()
        clear_layout(self.analytics_stats)
        total = data["total"]
        pct = round(data["completed"]*100/total) if total else 0
        self.analytics_stats.addWidget(self._stat_card(f"{data['completed']}/{total}","Activities completed",f"{pct}% roadmap completion"))
        self.analytics_stats.addWidget(self._stat_card(str(data["completed_projects"]),"Projects completed",f"{data['active_projects']} active of {data['project_total']} saved"))
        self.analytics_stats.addWidget(self._stat_card(str(data["review_count"]),"Portfolio reviews","Saved evaluation reports"))
        self.analytics_skill_chart.draw_skill_chart(data["skills"])
        self.analytics_progress_chart.draw_progress_chart(data["activities"])
        clear_layout(self.analytics_detail)
        self.analytics_detail.addWidget(heading(f"Active projects: {data['active_projects']}  |  Saved portfolio reviews: {data['review_count']}"))
        if data["reviews"]:
            for review in data["reviews"][:4]:
                review_card = Card()
                review_card.layout_box.addWidget(heading(review.project_name))
                review_card.layout_box.addWidget(heading(display_timestamp(review.created_at), "muted"))
                self.analytics_detail.addWidget(review_card)
        else:
            self.analytics_detail.addWidget(heading("Saved portfolio reviews will appear in this history.", "muted"))

    def _page_profile(self):
        page, layout = make_page()
        layout.addWidget(heading("My profile", "title"))
        layout.addWidget(heading("Your selected career is shared across the career check, skill gap, roadmap, project studio, and explorer.", "muted"))
        card = self._card("Student profile", "Saved to your account and this device")
        form = QFormLayout(); form.setSpacing(14)
        self.profile_name = QLineEdit()
        profile = self.db.get_profile()
        self.profile_goal = self._career_picker(profile.career_goal)
        self.profile_industry = self._industry_picker(profile.industry)
        self.profile_experience = QComboBox(); self.profile_experience.addItems(["Beginner","Intermediate","Advanced"])
        self.profile_interests = QLineEdit()
        self.profile_age = QLineEdit()
        self.profile_institution = QLineEdit()
        self.profile_country = QLineEdit()
        self.profile_region = QLineEdit()
        self.profile_career_interests = QLineEdit()
        self.profile_areas = QLineEdit()
        self.profile_preferences = QLineEdit()
        self.profile_availability = QLineEdit()
        self.profile_short_goal = QLineEdit()
        self.profile_long_goal = QLineEdit()
        self.profile_education = QLineEdit()
        self.profile_existing_skills = QLineEdit()
        form.addRow("Name", self.profile_name); form.addRow("Age range", self.profile_age)
        form.addRow("Career goal · searchable or custom", self.profile_goal); form.addRow("Industry · for custom careers", self.profile_industry)
        form.addRow("Other career interests · comma separated", self.profile_career_interests)
        form.addRow("Education level", self.profile_education); form.addRow("School / institution", self.profile_institution)
        form.addRow("Country", self.profile_country); form.addRow("Region / state", self.profile_region)
        form.addRow("Experience level", self.profile_experience); form.addRow("Interests · comma separated", self.profile_interests)
        form.addRow("Existing skills · comma separated", self.profile_existing_skills)
        form.addRow("Areas to improve · comma separated", self.profile_areas)
        form.addRow("Learning preferences", self.profile_preferences); form.addRow("Weekly availability", self.profile_availability)
        form.addRow("Short-term goal", self.profile_short_goal); form.addRow("Long-term goal", self.profile_long_goal)
        card.layout_box.addLayout(form)
        self.profile_save_button = make_button("Save profile", primary=True)
        self.profile_save_button.clicked.connect(self._save_profile)
        card.layout_box.addWidget(self.profile_save_button,0,Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)
        layout.addStretch(1)
        self._load_profile_fields()
        return page

    def _load_profile_fields(self):
        if not hasattr(self, "profile_name"): return
        profile = self.db.get_profile()
        self.profile_name.setText(profile.name)
        self.profile_goal.setCurrentText(profile.career_goal)
        self.profile_industry.setCurrentText(profile.industry)
        self.profile_experience.setCurrentText(profile.experience if profile.experience in ["Beginner","Intermediate","Advanced"] else "Beginner")
        self.profile_interests.setText(", ".join(profile.interests))
        self.profile_age.setText(profile.age_range); self.profile_institution.setText(profile.institution)
        self.profile_country.setText(profile.country); self.profile_region.setText(profile.region)
        self.profile_career_interests.setText(", ".join(profile.career_interests or []))
        self.profile_areas.setText(", ".join(profile.areas_to_improve or []))
        self.profile_preferences.setText(profile.learning_preferences)
        self.profile_availability.setText(profile.weekly_availability)
        self.profile_short_goal.setText(profile.short_term_goal); self.profile_long_goal.setText(profile.long_term_goal)
        self.profile_education.setText(profile.education_level)
        self.profile_existing_skills.setText(", ".join(profile.existing_skills or []))
        if hasattr(self, "career_goal_input"):
            self.career_goal_input.setCurrentText(profile.career_goal)
            self.career_industry.setCurrentText(profile.industry)
        if hasattr(self, "career_a"):
            self.career_a.setCurrentText(profile.career_goal)
            self.career_a_industry.setCurrentText(profile.industry)

    def _save_profile(self):
        interests = [item.strip() for item in self.profile_interests.text().split(",") if item.strip()]
        goal = self.profile_goal.currentText().strip()
        industry = infer_industry(goal, self.profile_industry.currentText())
        skills = [item.strip() for item in self.profile_existing_skills.text().split(",") if item.strip()]
        career_interests = [item.strip() for item in self.profile_career_interests.text().split(",") if item.strip()]
        areas = [item.strip() for item in self.profile_areas.text().split(",") if item.strip()]
        try:
            self.db.save_profile(self.profile_name.text(), goal, self.profile_education.text().strip(),
                                 self.profile_experience.currentText(), skills, industry=industry, interests=interests,
                                 age_range=self.profile_age.text(), institution=self.profile_institution.text(),
                                 country=self.profile_country.text(), region=self.profile_region.text(),
                                 career_interests=career_interests, areas_to_improve=areas,
                                 learning_preferences=self.profile_preferences.text(), weekly_availability=self.profile_availability.text(),
                                 short_term_goal=self.profile_short_goal.text(), long_term_goal=self.profile_long_goal.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Profile needs attention", str(exc)); return
        self._sync_profile_with_service()
        self._load_profile_fields()
        if hasattr(self, "career_goal_input"):
            self.career_goal_input.setCurrentText(goal); self.career_industry.setCurrentText(industry)
        if hasattr(self, "career_a"):
            self.career_a.setCurrentText(goal); self.career_a_industry.setCurrentText(industry)
        self._populate_skill_rows(); self._refresh_skill_chart(); self._refresh_roadmap()
        self.profile_button.setText(self.db.get_profile().name)
        self._refresh_dashboard(); self._refresh_analytics(); self._refresh_review_history()
        self._notify("Profile saved")

    def _start_ai(self, button, operation, args, callback, message, on_failure=None):
        if not self.gemini.enabled:
            self.navigate("Service & account")
            return
        if button:
            button.setEnabled(False)
            button.setText("Working…")
        self._notify(message)
        worker = AIWorker(operation, *args)
        self._workers.add(worker)
        prior_text = None
        if button:
            prior_text = getattr(button, "_prior_text", button.text())
            if not hasattr(button, "_prior_text"):
                button._prior_text = "Run reality check" if button is getattr(self,"career_button",None) else "Review my project" if button is getattr(self,"portfolio_review_button",None) else "Suggest roadmap updates" if button is getattr(self,"adapt_button",None) else "Generate project ideas" if button is getattr(self,"project_generate_button",None) else "Compare careers"
        def success(result):
            if button:
                button.setEnabled(True); button.setText(button._prior_text)
            try:
                callback(result)
            except Exception as exc:
                QMessageBox.warning(self, "Could not display result", str(exc))
                self._notify("The result could not be displayed")
        def failure(error):
            if button:
                button.setEnabled(True); button.setText(button._prior_text)
            if on_failure:
                on_failure(error)
            QMessageBox.warning(self, "Gemini request could not be completed", error)
            self._notify("AI request failed · see details")
        worker.succeeded.connect(success)
        worker.failed.connect(failure)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        worker.start()

    def _notify(self, message: str):
        self.status_label.setText(message)


def run_app():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
