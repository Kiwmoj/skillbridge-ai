"""SQLite persistence for real student profiles and Gemini-generated guidance."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from database.models import Activity, Profile, Project, Review, Skill

APP_ROOT = Path(__file__).resolve().parent.parent


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Database:
    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv("SKILLBRIDGE_DB_PATH")
        self.path = Path(configured) if configured else APP_ROOT / "data" / "skillbridge.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, factory=ClosingConnection)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def initialize(self) -> None:
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL DEFAULT '',
                    career_goal TEXT NOT NULL DEFAULT '', experience TEXT NOT NULL DEFAULT '',
                    interests TEXT NOT NULL DEFAULT '[]', demo_mode INTEGER NOT NULL DEFAULT 0,
                    industry TEXT NOT NULL DEFAULT 'Other / custom', education_level TEXT NOT NULL DEFAULT '',
                    existing_skills TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, proficiency INTEGER,
                    target INTEGER, importance TEXT NOT NULL DEFAULT 'Student reported',
                    explanation TEXT NOT NULL DEFAULT '', exercise TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY, stage TEXT NOT NULL, title TEXT NOT NULL,
                    description TEXT NOT NULL, skills TEXT NOT NULL DEFAULT '[]', duration TEXT NOT NULL,
                    difficulty TEXT NOT NULL, outcome TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Planned',
                    rationale TEXT NOT NULL DEFAULT '', career_goal TEXT NOT NULL, learning_objective TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL,
                    software TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'Saved',
                    is_demo INTEGER NOT NULL DEFAULT 0, details TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY, project_name TEXT NOT NULL, image_path TEXT NOT NULL DEFAULT '',
                    report TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0, career_goal TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS activity_log (id INTEGER PRIMARY KEY, message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS career_skills (
                    id INTEGER PRIMARY KEY, career_goal TEXT NOT NULL, name TEXT NOT NULL, proficiency INTEGER, target INTEGER,
                    importance TEXT NOT NULL DEFAULT 'Student reported', explanation TEXT NOT NULL DEFAULT '', exercise TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(career_goal,name)
                );
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY, career_goal TEXT NOT NULL, industry TEXT NOT NULL, kind TEXT NOT NULL,
                    source_mode TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self._migrate_columns(con)
            self._make_career_skills_nullable(con)
            self._remove_known_seed_profile(con)

    @staticmethod
    def _migrate_columns(con: sqlite3.Connection) -> None:
        additions = {
            "profiles": {"industry": "TEXT NOT NULL DEFAULT 'Other / custom'", "education_level": "TEXT NOT NULL DEFAULT ''", "existing_skills": "TEXT NOT NULL DEFAULT '[]'", "demo_mode": "INTEGER NOT NULL DEFAULT 0"},
            "activities": {"career_goal": "TEXT NOT NULL DEFAULT ''", "learning_objective": "TEXT NOT NULL DEFAULT ''"},
            "projects": {"details": "TEXT NOT NULL DEFAULT '{}'"},
            "reviews": {"career_goal": "TEXT NOT NULL DEFAULT ''"},
            "skills": {"exercise": "TEXT NOT NULL DEFAULT ''"},
        }
        for table, columns in additions.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        # Lift earlier profile-scoped records onto the original career before any picker changes it.
        profile = con.execute("SELECT career_goal FROM profiles WHERE id=1").fetchone()
        if profile:
            con.execute("UPDATE activities SET career_goal=? WHERE career_goal=''", (profile["career_goal"],))
            con.execute("UPDATE reviews SET career_goal=? WHERE career_goal=''", (profile["career_goal"],))

    @staticmethod
    def _make_career_skills_nullable(con: sqlite3.Connection) -> None:
        info = {row[1]: row for row in con.execute("PRAGMA table_info(career_skills)")}
        if info.get("proficiency") and info["proficiency"][3] or info.get("target") and info["target"][3]:
            con.execute("ALTER TABLE career_skills RENAME TO career_skills_old")
            con.execute("""CREATE TABLE career_skills (
                id INTEGER PRIMARY KEY, career_goal TEXT NOT NULL, name TEXT NOT NULL, proficiency INTEGER, target INTEGER,
                importance TEXT NOT NULL DEFAULT 'Student reported', explanation TEXT NOT NULL DEFAULT '', exercise TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(career_goal,name))""")
            old_cols = {row[1] for row in con.execute("PRAGMA table_info(career_skills_old)")}
            exercise = "exercise" if "exercise" in old_cols else "''"
            con.execute(f"INSERT OR IGNORE INTO career_skills(career_goal,name,proficiency,target,importance,explanation,exercise,updated_at) SELECT career_goal,name,proficiency,target,importance,explanation,{exercise},updated_at FROM career_skills_old")
            con.execute("DROP TABLE career_skills_old")

    @staticmethod
    def _remove_known_seed_profile(con: sqlite3.Connection) -> None:
        row = con.execute("SELECT * FROM profiles WHERE id=1").fetchone()
        if not row or row["name"] != "Alex Morgan" or not row["demo_mode"]:
            return
×´¶‰Ëkºwµçpü¤(€€€€€€€€€€€€€€€=8=91%P¡…É••É}½…°±¹…µ”¤<UAQMPÁÉ½™¥¥•¹äõ•á±Õ‘•¹ÁÉ½™¥¥•¹ä±Ñ…É•Ğõ•á±Õ‘•¹Ñ…É•Ğ°(€€€€€€€€€€€€€€€¥µÁ½ÉÑ…¹”õ•á±Õ‘•¹¥µÁ½ÉÑ…¹”±•áÁ±…¹…Ñ¥½¸õ•á±Õ‘•¹•áÁ±…¹…Ñ¥½¸±•á•É¥Í”õ•á±Õ‘•¹•á•É¥Í”±ÕÁ‘…Ñ•‘}…ĞõUII9Q}Q%5MQ5@ˆˆˆ°(€€€€€€€€€€€€€€€€¡…É••É}½…°±±•…¹}¹…µ”±É…Ñ¥¹œ¡ÁÉ½™¥¥•¹ä¤±É…Ñ¥¹œ¡Ñ…É•Ğ¤±¥µÁ½ÉÑ…¹”±•áÁ±…¹…Ñ¥½¸±•á•É¥Í”¤¤(€€€€€€€€€€€Í•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰M­¥±°…ÍÍ•ÍÍµ•¹ĞÕÁ‘…Ñ•ğí…É••É}½…±ôğí±•…¹}¹…µ•ôˆ¤((€€€‘•˜•Ñ}…Ñ¥Ù¥Ñ¥•Ì¡Í•±˜°…É••É}½…°èÍÑÈğ9½¹”€ô9½¹”¤€´ø±¥ÍÑmÑ¥Ù¥Ñåtè(€€€€€€€…É••É}½…°€ô…É••É}½…°½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€¥˜¹½Ğ…É••É}½…°èÉ•ÑÕÉ¸mt(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€É½İÌ€ô½¸¹•á•ÕÑ” ‰M1P€¨I=4…Ñ¥Ù¥Ñ¥•Ì]!I…É••É}½…°ôü=IH	dMÍÑ…”]!8€	•¥¹¹•ÈœQ!8€Ä]!8€%¹Ñ•Éµ•‘¥…Ñ”œQ!8€È1M€Ì9±¥ˆ°€¡…É••É}½…°°¤¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸mÑ¥Ù¥Ñä¡Él‰¥‰t±Él‰ÍÑ…”‰t±Él‰Ñ¥Ñ±”‰t±Él‰‘•ÍÉ¥ÁÑ¥½¸‰t±©Í½¸¹±½…‘Ì¡Él‰Í­¥±±Ì‰t¤±Él‰‘ÕÉ…Ñ¥½¸‰t±Él‰‘¥™™¥Õ±Ñä‰t±Él‰½ÕÑ½µ”‰t±Él‰ÍÑ…ÑÕÌ‰t±Él‰É…Ñ¥½¹…±”‰t±Él‰…É••É}½…°‰t±Él‰±•…É¹¥¹}½‰©•Ñ¥Ù”‰t¤™½ÈÈ¥¸É½İÍt((€€€‘•˜ÕÁ‘…Ñ•}…Ñ¥Ù¥Ñå}ÍÑ…ÑÕÌ¡Í•±˜°…Ñ¥Ù¥Ñå}¥è¥¹Ğ°ÍÑ…ÑÕÌèÍÑÈ¤€´ø9½¹”è(€€€€€€€¥˜ÍÑ…ÑÕÌ¹½Ğ¥¸ì‰A±…¹¹•ˆ°‰%¸ÁÉ½É•ÍÌˆ°‰½µÁ±•Ñ•‰ôèÉ…¥Í”Y…±Õ•ÉÉ½È ‰U¹­¹½İ¸…Ñ¥Ù¥ÑäÍÑ…ÑÕÌˆ¤(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€½¸¹•á•ÕÑ” ‰UAQ…Ñ¥Ù¥Ñ¥•ÌMPÍÑ…ÑÕÌôü]!I¥ôüˆ°€¡ÍÑ…ÑÕÌ±…Ñ¥Ù¥Ñå}¥¤¤(€€€€€€€€€€€É½Ü€ô½¸¹•á•ÕÑ” ‰M1PÑ¥Ñ±”I=4…Ñ¥Ù¥Ñ¥•Ì]!I¥ôüˆ°€¡…Ñ¥Ù¥Ñå}¥°¤¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½ÜèÍ•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰I½…‘µ…À…Ñ¥Ù¥ÑäíÍÑ…ÑÕÌ¹±½İ•È ¥ôğíÉ½İlÑ¥Ñ±”uôˆ¤((€€€‘•˜…‘‘}…Ñ¥Ù¥Ñä¡Í•±˜°¥Ñ•´è‘¥ÑmÍÑÈ°¹åt¤€´ø¥¹Ğè(€€€€€€€½…°€ô¥Ñ•´¹•Ğ ‰…É••É}½…°ˆ¤½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€ÕÈ€ô½¸¹•á•ÕÑ” ˆˆ‰%9MIP%9Q<…Ñ¥Ù¥Ñ¥•Ì¡ÍÑ…”±Ñ¥Ñ±”±‘•ÍÉ¥ÁÑ¥½¸±Í­¥±±Ì±‘ÕÉ…Ñ¥½¸±‘¥™™¥Õ±Ñä±½ÕÑ½µ”±ÍÑ…ÑÕÌ±É…Ñ¥½¹…±”±…É••É}½…°±±•…É¹¥¹}½‰©•Ñ¥Ù”¤(€€€€€€€€€€€€€€€Y1UL ü°ü°ü°ü°ü°ü°ü°A±…¹¹•œ°ü°ü°ü¤ˆˆˆ°€¡¥Ñ•µl‰ÍÑ…”‰t±¥Ñ•µl‰Ñ¥Ñ±”‰t±¥Ñ•µl‰‘•ÍÉ¥ÁÑ¥½¸‰t±©Í½¸¹‘ÕµÁÌ¡¥Ñ•´¹•Ğ ‰Í­¥±±Ìˆ±mt¤¤°(€€€€€€€€€€€€€€€¥Ñ•µl‰‘ÕÉ…Ñ¥½¸‰t±¥Ñ•µl‰‘¥™™¥Õ±Ñä‰t±¥Ñ•µl‰½ÕÑ½µ”‰t±¥Ñ•´¹•Ğ ‰É…Ñ¥½¹…±”ˆ°ˆˆ¤±½…°±¥Ñ•´¹•Ğ ‰±•…É¹¥¹}½‰©•Ñ¥Ù”ˆ°ˆˆ¤¤¤(€€€€€€€€€€€Í•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰I½…‘µ…ÀÕÁ‘…Ñ•ğí½…±ôğí¥Ñ•µlÑ¥Ñ±”uôˆ¤(€€€€€€€€€€€É•ÑÕÉ¸¥¹Ğ¡ÕÈ¹±…ÍÑÉ½İ¥¤((€€€‘•˜…‘‘}É•½µµ•¹‘…Ñ¥½¸¡Í•±˜°…É••É}½…°èÍÑÈ°¥¹‘ÕÍÑÉäèÍÑÈ°­¥¹èÍÑÈ°½¹Ñ•¹Ğè¹ä°Í½ÕÉ•}µ½‘”èÍÑÈ€ô€‰1%Y5%9$A$ˆ¤€´ø¥¹Ğè(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€ÕÈ€ô½¸¹•á•ÕÑ” ‰%9MIP%9Q<É•½µµ•¹‘…Ñ¥½¹Ì¡…É••É}½…°±¥¹‘ÕÍÑÉä±­¥¹±Í½ÕÉ•}µ½‘”±½¹Ñ•¹Ğ¤Y1UL ü°ü°ü°ü°ü¤ˆ°€¡…É••É}½…°±¥¹‘ÕÍÑÉä±­¥¹±Í½ÕÉ•}µ½‘”±©Í½¸¹‘ÕµÁÌ¡½¹Ñ•¹Ğ±•¹ÍÕÉ•}…Í¥¤õ…±Í”¤¤¤(€€€€€€€€€€€Í•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰í­¥¹¹É•Á±…” |œ°œ€œ¤¹Ñ¥Ñ±” ¥ôÍ…Ù•ğí…É••É}½…±ôˆ¤(€€€€€€€€€€€É•ÑÕÉ¸¥¹Ğ¡ÕÈ¹±…ÍÑÉ½İ¥¤((€€€‘•˜•Ñ}É•½µµ•¹‘…Ñ¥½¹Ì¡Í•±˜°…É••É}½…°èÍÑÈğ9½¹”€ô9½¹”°­¥¹èÍÑÈğ9½¹”€ô9½¹”¤€´ø±¥ÍÑm‘¥ÑmÍÑÈ°¹åutè(€€€€€€€ÅÕ•Éä°Á…É…µÌ€ô€‰M1P€¨I=4É•½µµ•¹‘…Ñ¥½¹Ì]!I€ÄôÄˆ°mt(€€€€€€€¥˜…É••É}½…°¥Ì¹½Ğ9½¹”èÅÕ•Éä€¬ô€ˆ9…É••É}½…°ôüˆìÁ…É…µÌ¹…ÁÁ•¹¡…É••É}½…°¤(€€€€€€€¥˜­¥¹¥Ì¹½Ğ9½¹”èÅÕ•Éä€¬ô€ˆ9­¥¹ôüˆìÁ…É…µÌ¹…ÁÁ•¹¡­¥¹¤(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸èÉ½İÌ€ô½¸¹•á•ÕÑ”¡ÅÕ•Éä¬ˆ=IH	dÉ•…Ñ•‘}…ĞM±¥Mˆ±Á…É…µÌ¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸mì‰¥ˆéÉl‰¥‰t°‰…É••É}½…°ˆéÉl‰…É••É}½…°‰t°‰¥¹‘ÕÍÑÉäˆéÉl‰¥¹‘ÕÍÑÉä‰t°‰­¥¹ˆéÉl‰­¥¹‰t°‰Í½ÕÉ•}µ½‘”ˆéÉl‰Í½ÕÉ•}µ½‘”‰t°‰½¹Ñ•¹Ğˆé©Í½¸¹±½…‘Ì¡Él‰½¹Ñ•¹Ğ‰t¤°‰É•…Ñ•‘}…ĞˆéÉl‰É•…Ñ•‘}…Ğ‰uô™½ÈÈ¥¸É½İÍt((€€€‘•˜…‘‘}ÁÉ½©•Ğ¡Í•±˜°¥Ñ•´è‘¥ÑmÍÑÈ°¹åt¤€´ø¥¹Ğè(€€€€€€€½…°€ô¥Ñ•´¹•Ğ ‰…Ñ•½Éäˆ¤½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€ÕÈ€ô½¸¹•á•ÕÑ” ‰%9MIP%9Q<ÁÉ½©•ÑÌ¡Ñ¥Ñ±”±‘•ÍÉ¥ÁÑ¥½¸±…Ñ•½Éä±Í½™Ñİ…É”±Í­¥±±Ì±ÍÑ…ÑÕÌ±¥Í}‘•µ¼±‘•Ñ…¥±Ì¤Y1UL ü°ü°ü°ü°ü°M…Ù•œ°À°ü¤ˆ°€¡¥Ñ•µl‰Ñ¥Ñ±”‰t±¥Ñ•µl‰‘•ÍÉ¥ÁÑ¥½¸‰t±½…°±¥Ñ•´¹•Ğ ‰Í½™Ñİ…É”ˆ°ˆˆ¤±©Í½¸¹‘ÕµÁÌ¡¥Ñ•´¹•Ğ ‰Í­¥±±Ìˆ±mt¤¤±©Í½¸¹‘ÕµÁÌ¡¥Ñ•´¹•Ğ ‰‘•Ñ…¥±Ìˆ±íô¤¤¤¤(€€€€€€€€€€€Í•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰AÉ½©•ĞÍ…Ù•ğí¥Ñ•µlÑ¥Ñ±”uôˆ¤(€€€€€€€€€€€É•ÑÕÉ¸¥¹Ğ¡ÕÈ¹±…ÍÑÉ½İ¥¤((€€€‘•˜•Ñ}ÁÉ½©•ÑÌ¡Í•±˜°…É••É}½…°èÍÑÈğ9½¹”€ô9½¹”¤€´ø±¥ÍÑmAÉ½©•Ñtè(€€€€€€€½…°€ô…É••É}½…°½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€¥˜¹½Ğ½…°èÉ•ÑÕÉ¸mt(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸èÉ½İÌ€ô½¸¹•á•ÕÑ” ‰M1P€¨I=4ÁÉ½©•ÑÌ]!I…Ñ•½Éäôü=IH	dÉ•…Ñ•‘}…ĞM±¥Mˆ°€¡½…°°¤¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸mAÉ½©•Ğ¡Él‰¥‰t±Él‰Ñ¥Ñ±”‰t±Él‰‘•ÍÉ¥ÁÑ¥½¸‰t±Él‰…Ñ•½Éä‰t±Él‰Í½™Ñİ…É”‰t±©Í½¸¹±½…‘Ì¡Él‰Í­¥±±Ì‰t¤±Él‰ÍÑ…ÑÕÌ‰t±©Í½¸¹±½…‘Ì¡Él‰‘•Ñ…¥±Ì‰t¤¤™½ÈÈ¥¸É½İÍt((€€€‘•˜ÕÁ‘…Ñ•}ÁÉ½©•Ñ}ÍÑ…ÑÕÌ¡Í•±˜°ÁÉ½©•Ñ}¥è¥¹Ğ°ÍÑ…ÑÕÌèÍÑÈ¤€´ø9½¹”è(€€€€€€€¥˜ÍÑ…ÑÕÌ¹½Ğ¥¸ì‰M…Ù•ˆ°‰%¸ÁÉ½É•ÍÌˆ°‰½µÁ±•Ñ•‰ôèÉ…¥Í”Y…±Õ•ÉÉ½È ‰U¹­¹½İ¸ÁÉ½©•ĞÍÑ…ÑÕÌˆ¤(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€½¸¹•á•ÕÑ” ‰UAQÁÉ½©•ÑÌMPÍÑ…ÑÕÌôü]!I¥ôüˆ°€¡ÍÑ…ÑÕÌ±ÁÉ½©•Ñ}¥¤¤(€€€€€€€€€€€É½Ü€ô½¸¹•á•ÕÑ” ‰M1PÑ¥Ñ±”I=4ÁÉ½©•ÑÌ]!I¥ôüˆ°€¡ÁÉ½©•Ñ}¥°¤¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½ÜèÍ•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰AÉ½©•Ğµ…É­•íÍÑ…ÑÕÌ¹±½İ•È ¥ôğíÉ½İlÑ¥Ñ±”uôˆ¤((€€€‘•˜…‘‘}É•Ù¥•Ü¡Í•±˜°ÁÉ½©•Ñ}¹…µ”èÍÑÈ°¥µ…•}Á…Ñ èÍÑÈ°É•Á½ÉĞè‘¥ÑmÍÑÈ°¹åt°…É••É}½…°èÍÑÈğ9½¹”€ô9½¹”¤€´ø¥¹Ğè(€€€€€€€½…°€ô…É••É}½…°½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€ÕÈ€ô½¸¹•á•ÕÑ” ‰%9MIP%9Q<É•Ù¥•İÌ¡ÁÉ½©•Ñ}¹…µ”±¥µ…•}Á…Ñ ±É•Á½ÉĞ±¥Í}‘•µ¼±…É••É}½…°¤Y1UL ü°ü°ü°À°ü¤ˆ°€¡ÁÉ½©•Ñ}¹…µ”±¥µ…•}Á…Ñ ±©Í½¸¹‘ÕµÁÌ¡É•Á½ÉĞ±•¹ÍÕÉ•}…Í¥¤õ…±Í”¤±½…°¤¤(€€€€€€€€€€€Í•±˜¹}İÉ¥Ñ•}±½œ¡½¸°˜‰A½ÉÑ™½±¥¼É•Ù¥•ÜÍ…Ù•ğíÁÉ½©•Ñ}¹…µ•ôˆ¤(€€€€€€€€€€€É•ÑÕÉ¸¥¹Ğ¡ÕÈ¹±…ÍÑÉ½İ¥¤((€€€‘•˜•Ñ}É•Ù¥•İÌ¡Í•±˜°…É••É}½…°èÍÑÈğ9½¹”€ô9½¹”¤€´ø±¥ÍÑmI•Ù¥•İtè(€€€€€€€½…°€ô…É••É}½…°½ÈÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€¥˜¹½Ğ½…°èÉ•ÑÕÉ¸mt(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸èÉ½İÌ€ô½¸¹•á•ÕÑ” ‰M1P€¨I=4É•Ù¥•İÌ]!I…É••É}½…°ôü=IH	dÉ•…Ñ•‘}…ĞM±¥Mˆ°€¡½…°°¤¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸mI•Ù¥•Ü¡Él‰¥‰t±Él‰ÁÉ½©•Ñ}¹…µ”‰t±Él‰É•…Ñ•‘}…Ğ‰t±©Í½¸¹±½…‘Ì¡Él‰É•Á½ÉĞ‰t¤±Él‰¥µ…•}Á…Ñ ‰t±Él‰…É••É}½…°‰t¤™½ÈÈ¥¸É½İÍt((€€€‘•˜±½œ¡Í•±˜°µ•ÍÍ…”èÍÑÈ¤€´ø9½¹”è(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸èÍ•±˜¹}İÉ¥Ñ•}±½œ¡½¸±µ•ÍÍ…”¤((€€€‘•˜•Ñ}É••¹Ñ}…Ñ¥Ù¥Ñä¡Í•±˜°±¥µ¥Ğè¥¹Ğ€ô€à¤€´ø±¥ÍÑmÑÕÁ±•mÍÑÈ±ÍÑÉutè(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸èÉ½İÌ€ô½¸¹•á•ÕÑ” ‰M1Pµ•ÍÍ…”±É•…Ñ•‘}…ĞI=4…Ñ¥Ù¥Ñå}±½œ=IH	d¥M1%5%P€üˆ°¡±¥µ¥Ğ°¤¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸l¡Él‰µ•ÍÍ…”‰t±Él‰É•…Ñ•‘}…Ğ‰t¤™½ÈÈ¥¸É½İÍt((€€€‘•˜…¹…±åÑ¥Ì¡Í•±˜¤€´ø‘¥ÑmÍÑÈ°¹åtè(€€€€€€€½…°€ôÍ•±˜¹•Ñ}ÁÉ½™¥±” ¤¹…É••É}½…°(€€€€€€€¥˜¹½Ğ½…°èÉ•ÑÕÉ¸ì‰½µÁ±•Ñ•ˆèÀ°‰Ñ½Ñ…°ˆèÀ°‰…Ñ¥Ù•}ÁÉ½©•ÑÌˆèÀ°‰½µÁ±•Ñ•‘}ÁÉ½©•ÑÌˆèÀ°‰ÁÉ½©•Ñ}Ñ½Ñ…°ˆèÀ°‰É•Ù¥•İ}½Õ¹ĞˆèÀ°‰Í­¥±±Ìˆémt°‰…Ñ¥Ù¥Ñ¥•Ìˆémt°‰É•Ù¥•İÌˆémuô(€€€€€€€İ¥Ñ Í•±˜¹½¹¹•Ğ ¤…Ì½¸è(€€€€€€€€€€€½µÁ±•Ñ•€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4…Ñ¥Ù¥Ñ¥•Ì]!I…É••É}½…°ôü9ÍÑ…ÑÕÌô½µÁ±•Ñ•œˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€Ñ½Ñ…°€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4…Ñ¥Ù¥Ñ¥•Ì]!I…É••É}½…°ôüˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€…Ñ¥Ù”€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4ÁÉ½©•ÑÌ]!I…Ñ•½Éäôü9ÍÑ…ÑÕÌ„ô½µÁ±•Ñ•œˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€ÁÉ½©•Ñ}Ñ½Ñ…°€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4ÁÉ½©•ÑÌ]!I…Ñ•½Éäôüˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€½µÁ±•Ñ•‘}ÁÉ½©•ÑÌ€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4ÁÉ½©•ÑÌ]!I…Ñ•½Éäôü9ÍÑ…ÑÕÌô½µÁ±•Ñ•œˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€€€€€É•Ù¥•İ}½Õ¹Ğ€ô½¸¹•á•ÕÑ” ‰M1P=U9P ¨¤I=4É•Ù¥•İÌ]!I…É••É}½…°ôüˆ°¡½…°°¤¤¹™•Ñ¡½¹” ¥lÁt(€€€€€€€É•ÑÕÉ¸ì‰½µÁ±•Ñ•ˆé½µÁ±•Ñ•°‰Ñ½Ñ…°ˆéÑ½Ñ…°°‰…Ñ¥Ù•}ÁÉ½©•ÑÌˆé…Ñ¥Ù”°‰½µÁ±•Ñ•‘}ÁÉ½©•ÑÌˆé½µÁ±•Ñ•‘}ÁÉ½©•ÑÌ°‰ÁÉ½©•Ñ}Ñ½Ñ…°ˆéÁÉ½©•Ñ}Ñ½Ñ…°°‰É•Ù¥•İ}½Õ¹ĞˆéÉ•Ù¥•İ}½Õ¹Ğ°‰Í­¥±±ÌˆéÍ•±˜¹•Ñ}Í­¥±±Ì¡½…°¤°‰…Ñ¥Ù¥Ñ¥•ÌˆéÍ•±˜¹•Ñ}…Ñ¥Ù¥Ñ¥•Ì¡½…°¤°‰É•Ù¥•İÌˆéÍ•±˜¹•Ñ}É•Ù¥•İÌ¡½…°¥ô