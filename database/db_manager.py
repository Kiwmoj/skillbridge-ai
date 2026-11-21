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
                    existing_skills TEXT NOT NULL DEFAULT '[]', age_range TEXT NOT NULL DEFAULT '',
                    institution TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT '', region TEXT NOT NULL DEFAULT '',
                    career_interests TEXT NOT NULL DEFAULT '[]', areas_to_improve TEXT NOT NULL DEFAULT '[]',
                    learning_preferences TEXT NOT NULL DEFAULT '', weekly_availability TEXT NOT NULL DEFAULT '',
                    short_term_goal TEXT NOT NULL DEFAULT '', long_term_goal TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                    notes TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
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
            "profiles": {"industry": "TEXT NOT NULL DEFAULT 'Other / custom'", "education_level": "TEXT NOT NULL DEFAULT ''", "existing_skills": "TEXT NOT NULL DEFAULT '[]'", "demo_mode": "INTEGER NOT NULL DEFAULT 0", "age_range": "TEXT NOT NULL DEFAULT ''", "institution": "TEXT NOT NULL DEFAULT ''", "country": "TEXT NOT NULL DEFAULT ''", "region": "TEXT NOT NULL DEFAULT ''", "career_interests": "TEXT NOT NULL DEFAULT '[]'", "areas_to_improve": "TEXT NOT NULL DEFAULT '[]'", "learning_preferences": "TEXT NOT NULL DEFAULT ''", "weekly_availability": "TEXT NOT NULL DEFAULT ''", "short_term_goal": "TEXT NOT NULL DEFAULT ''", "long_term_goal": "TEXT NOT NULL DEFAULT ''"},
            "activities": {"career_goal": "TEXT NOT NULL DEFAULT ''", "learning_objective": "TEXT NOT NULL DEFAULT ''", "notes": "TEXT NOT NULL DEFAULT ''", "sort_order": "INTEGER NOT NULL DEFAULT 0"},
            "projects": {"details": "TEXT NOT NULL DEFAULT '{}'"},
            "reviews": {"career_goal": "TEXT NOT NULL DEFAULT ''"},
            "skills": {"exercise": "TEXT NOT NULL DEFAULT ''"},
        }
        for table, columns in additions.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        ordered = con.execute("SELECT id,career_goal,stage FROM activities ORDER BY career_goal,stage,sort_order,id").fetchall()
        positions: dict[tuple[str, str], int] = {}
        for activity in ordered:
            key = (activity["career_goal"], activity["stage"])
            position = positions.get(key, 0)
            con.execute("UPDATE activities SET sort_order=? WHERE id=?", (position, activity["id"]))
            positions[key] = position + 1
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
        try:
            interests = json.loads(row["interests"] or "[]")
        except (ValueError, TypeError):
            return
        known_interests = {
            ("3D character modeling", "Character animation", "Game development", "Animation storytelling"),
            ("Problem solving", "Creative thinking", "Research"),
        }
        if tuple(interests) not in known_interests:
            return
        for table in ("activity_log", "recommendations", "reviews", "projects", "activities", "career_skills", "skills", "profiles"):
            con.execute(f"DELETE FROM {table}")

    @staticmethod
    def _write_log(con: sqlite3.Connection, message: str) -> None:
        con.execute("INSERT INTO activity_log(message) VALUES(?)", (message,))

    def has_profile(self) -> bool:
        with self.connect() as con:
            row = con.execute("SELECT name,career_goal FROM profiles WHERE id=1").fetchone()
        return bool(row and row["name"].strip() and row["career_goal"].strip())

    def get_profile(self) -> Profile:
        with self.connect() as con:
            row = con.execute("SELECT * FROM profiles WHERE id=1").fetchone()
        if not row:
            return Profile("", "", "", [])
        def load_list(key: str) -> list[str]:
            try: return json.loads(row[key] or "[]")
            except (ValueError, TypeError): return []
        return Profile(name=row["name"], career_goal=row["career_goal"], experience=row["experience"],
                       interests=load_list("interests"), industry=row["industry"],
                       education_level=row["education_level"], existing_skills=load_list("existing_skills"),
                       age_range=row["age_range"], institution=row["institution"], country=row["country"],
                       region=row["region"], career_interests=load_list("career_interests"),
                       areas_to_improve=load_list("areas_to_improve"),
                       learning_preferences=row["learning_preferences"], weekly_availability=row["weekly_availability"],
                       short_term_goal=row["short_term_goal"], long_term_goal=row["long_term_goal"])

    def save_profile(self, name: str, goal: str, education_level: str, experience: str,
                     existing_skills: list[str], industry: str = "", interests: list[str] | None = None,
                     age_range: str = "", institution: str = "", country: str = "", region: str = "",
                     career_interests: list[str] | None = None, areas_to_improve: list[str] | None = None,
                     learning_preferences: str = "", weekly_availability: str = "",
                     short_term_goal: str = "", long_term_goal: str = "") -> None:
        from services.career_catalog import infer_industry
        name, goal = name.strip(), goal.strip()
        if not name or not goal:
            raise ValueError("Enter your name and a career goal to save your profile.")
        selected_industry = infer_industry(goal, industry)
        skill_names = list(dict.fromkeys(s.strip() for s in existing_skills if s.strip()))
        with self.connect() as con:
            con.execute("""INSERT INTO profiles(id,name,career_goal,experience,interests,demo_mode,industry,education_level,existing_skills,
                age_range,institution,country,region,career_interests,areas_to_improve,learning_preferences,weekly_availability,short_term_goal,long_term_goal,updated_at)
                VALUES(1,?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,career_goal=excluded.career_goal,experience=excluded.experience,interests=excluded.interests,
                demo_mode=0,industry=excluded.industry,education_level=excluded.education_level,existing_skills=excluded.existing_skills,
                age_range=excluded.age_range,institution=excluded.institution,country=excluded.country,region=excluded.region,
                career_interests=excluded.career_interests,areas_to_improve=excluded.areas_to_improve,
                learning_preferences=excluded.learning_preferences,weekly_availability=excluded.weekly_availability,
                short_term_goal=excluded.short_term_goal,long_term_goal=excluded.long_term_goal,updated_at=CURRENT_TIMESTAMP""",
                (name, goal, experience, json.dumps(interests or []), selected_industry, education_level, json.dumps(skill_names),
                 age_range.strip(), institution.strip(), country.strip(), region.strip(),
                 json.dumps(career_interests or []), json.dumps(areas_to_improve or []), learning_preferences.strip(),
                 weekly_availability.strip(), short_term_goal.strip(), long_term_goal.strip()))
            # Preserve existing records under their former career; add only student-entered skills to this career.
            for skill in skill_names:
                con.execute("INSERT OR IGNORE INTO career_skills(career_goal,name) VALUES(?,?)", (goal, skill))
            self._write_log(con, f"Student profile saved | career: {goal}")

    def get_skills(self, career_goal: str | None = None, industry: str | None = None) -> list[Skill]:
        career_goal = career_goal or self.get_profile().career_goal
        if not career_goal: return []
        with self.connect() as con:
            rows = con.execute("SELECT * FROM career_skills WHERE career_goal=? ORDER BY importance='Essential' DESC,name", (career_goal,)).fetchall()
        return [Skill(r["name"],r["proficiency"],r["target"],r["importance"],r["explanation"],r["exercise"]) for r in rows]

    def save_skill(self, name: str, proficiency: int | None = None, target: int | None = None,
                   importance: str = "Student reported", explanation: str = "", exercise: str = "", career_goal: str | None = None) -> None:
        career_goal = career_goal or self.get_profile().career_goal
        clean_name = name.strip()
        if not clean_name or not career_goal: raise ValueError("A career and skill name are required.")
        def rating(value): return None if value is None else max(0, min(100, int(value)))
        with self.connect() as con:
            con.execute("""INSERT INTO career_skills(career_goal,name,proficiency,target,importance,explanation,exercise) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(career_goal,name) DO UPDATE SET proficiency=excluded.proficiency,target=excluded.target,
                importance=excluded.importance,explanation=excluded.explanation,exercise=excluded.exercise,updated_at=CURRENT_TIMESTAMP""",
                (career_goal,clean_name,rating(proficiency),rating(target),importance,explanation,exercise))
            self._write_log(con, f"Skill assessment updated | {career_goal} | {clean_name}")

    def get_activities(self, career_goal: str | None = None) -> list[Activity]:
        career_goal = career_goal or self.get_profile().career_goal
        if not career_goal: return []
        with self.connect() as con:
            rows = con.execute("SELECT * FROM activities WHERE career_goal=? ORDER BY CASE stage WHEN 'Beginner' THEN 1 WHEN 'Intermediate' THEN 2 ELSE 3 END,sort_order,id", (career_goal,)).fetchall()
        return [Activity(r["id"],r["stage"],r["title"],r["description"],json.loads(r["skills"]),r["duration"],r["difficulty"],r["outcome"],r["status"],r["rationale"],r["career_goal"],r["learning_objective"],r["notes"],r["sort_order"]) for r in rows]

    def update_activity_status(self, activity_id: int, status: str) -> None:
        if status not in {"Planned","In progress","Paused","Completed"}: raise ValueError("Unknown activity status")
        with self.connect() as con:
            con.execute("UPDATE activities SET status=? WHERE id=?", (status,activity_id))
            row = con.execute("SELECT title FROM activities WHERE id=?", (activity_id,)).fetchone()
            if row: self._write_log(con, f"Roadmap activity {status.lower()} | {row['title']}")

    def add_activity(self, item: dict[str, Any]) -> int:
        goal = item.get("career_goal") or self.get_profile().career_goal
        with self.connect() as con:
            order = con.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM activities WHERE career_goal=? AND stage=?", (goal,item["stage"])).fetchone()[0]
            cur = con.execute("""INSERT INTO activities(stage,title,description,skills,duration,difficulty,outcome,status,rationale,career_goal,learning_objective,notes,sort_order)
                VALUES(?,?,?,?,?,?,?,'Planned',?,?,?,?,?)""", (item["stage"],item["title"],item["description"],json.dumps(item.get("skills",[])),
                item["duration"],item["difficulty"],item["outcome"],item.get("rationale",""),goal,item.get("learning_objective",""),item.get("notes",""),item.get("sort_order",order)))
            self._write_log(con, f"Roadmap updated | {goal} | {item['title']}")
            return int(cur.lastrowid)

    def update_activity(self, activity_id: int, *, title: str, description: str, learning_objective: str,
                        duration: str, outcome: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("An activity title is required.")
        with self.connect() as con:
            con.execute("UPDATE activities SET title=?,description=?,learning_objective=?,duration=?,outcome=? WHERE id=?",
                        (title,description.strip(),learning_objective.strip(),duration.strip(),outcome.strip(),activity_id))
            self._write_log(con, f"Roadmap activity edited | {title}")

    def update_activity_notes(self, activity_id: int, notes: str) -> None:
        with self.connect() as con:
            con.execute("UPDATE activities SET notes=? WHERE id=?", (notes.strip()[:4000],activity_id))

    def move_activity(self, activity_id: int, direction: int) -> None:
        if direction not in {-1, 1}:
            raise ValueError("Move direction must be -1 or 1.")
        with self.connect() as con:
            current = con.execute("SELECT id,career_goal,stage,sort_order FROM activities WHERE id=?", (activity_id,)).fetchone()
            if not current:
                return
            comparator = "<" if direction < 0 else ">"
            ordering = "DESC" if direction < 0 else "ASC"
            neighbor = con.execute(f"SELECT id,sort_order FROM activities WHERE career_goal=? AND stage=? AND sort_order {comparator} ? ORDER BY sort_order {ordering} LIMIT 1",
                                   (current["career_goal"],current["stage"],current["sort_order"])).fetchone()
            if not neighbor:
                return
            con.execute("UPDATE activities SET sort_order=-1 WHERE id=?", (current["id"],))
            con.execute("UPDATE activities SET sort_order=? WHERE id=?", (current["sort_order"],neighbor["id"]))
            con.execute("UPDATE activities SET sort_order=? WHERE id=?", (neighbor["sort_order"],current["id"]))

    def clear_activities(self, career_goal: str | None = None) -> None:
        goal = career_goal or self.get_profile().career_goal
        with self.connect() as con:
            con.execute("DELETE FROM activities WHERE career_goal=?", (goal,))
            self._write_log(con, f"Roadmap replaced | {goal}")

    def add_recommendation(self, career_goal: str, industry: str, kind: str, content: Any, source_mode: str = "LIVE GEMINI API") -> int:
        with self.connect() as con:
            cur = con.execute("INSERT INTO recommendations(career_goal,industry,kind,source_mode,content) VALUES(?,?,?,?,?)", (career_goal,industry,kind,source_mode,json.dumps(content,ensure_ascii=False)))
            self._write_log(con, f"{kind.replace('_',' ').title()} saved | {career_goal}")
            return int(cur.lastrowid)

    def get_recommendations(self, career_goal: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        query, params = "SELECT * FROM recommendations WHERE 1=1", []
        if career_goal is not None: query += " AND career_goal=?"; params.append(career_goal)
        if kind is not None: query += " AND kind=?"; params.append(kind)
        with self.connect() as con: rows = con.execute(query+" ORDER BY created_at DESC,id DESC",params).fetchall()
        return [{"id":r["id"],"career_goal":r["career_goal"],"industry":r["industry"],"kind":r["kind"],"source_mode":r["source_mode"],"content":json.loads(r["content"]),"created_at":r["created_at"]} for r in rows]

    def add_project(self, item: dict[str, Any]) -> int:
        goal = item.get("category") or self.get_profile().career_goal
        with self.connect() as con:
            cur = con.execute("INSERT INTO projects(title,description,category,software,skills,status,is_demo,details) VALUES(?,?,?,?,?,'Saved',0,?)", (item["title"],item["description"],goal,item.get("software",""),json.dumps(item.get("skills",[])),json.dumps(item.get("details",{}))))
            self._write_log(con, f"Project saved | {item['title']}")
            return int(cur.lastrowid)

    def get_projects(self, career_goal: str | None = None) -> list[Project]:
        goal = career_goal or self.get_profile().career_goal
        if not goal: return []
        with self.connect() as con: rows = con.execute("SELECT * FROM projects WHERE category=? ORDER BY created_at DESC,id DESC", (goal,)).fetchall()
        return [Project(r["id"],r["title"],r["description"],r["category"],r["software"],json.loads(r["skills"]),r["status"],json.loads(r["details"])) for r in rows]

    def update_project_status(self, project_id: int, status: str) -> None:
        if status not in {"Saved","In progress","Completed"}: raise ValueError("Unknown project status")
        with self.connect() as con:
            con.execute("UPDATE projects SET status=? WHERE id=?", (status,project_id))
            row = con.execute("SELECT title FROM projects WHERE id=?", (project_id,)).fetchone()
            if row: self._write_log(con, f"Project marked {status.lower()} | {row['title']}")

    def add_review(self, project_name: str, image_path: str, report: dict[str, Any], career_goal: str | None = None) -> int:
        goal = career_goal or self.get_profile().career_goal
        with self.connect() as con:
            cur = con.execute("INSERT INTO reviews(project_name,image_path,report,is_demo,career_goal) VALUES(?,?,?,0,?)", (project_name,image_path,json.dumps(report,ensure_ascii=False),goal))
            self._write_log(con, f"Portfolio review saved | {project_name}")
            return int(cur.lastrowid)

    def get_reviews(self, career_goal: str | None = None) -> list[Review]:
        goal = career_goal or self.get_profile().career_goal
        if not goal: return []
        with self.connect() as con: rows = con.execute("SELECT * FROM reviews WHERE career_goal=? ORDER BY created_at DESC,id DESC", (goal,)).fetchall()
        return [Review(r["id"],r["project_name"],r["created_at"],json.loads(r["report"]),r["image_path"],r["career_goal"]) for r in rows]

    def log(self, message: str) -> None:
        with self.connect() as con: self._write_log(con,message)

    def get_recent_activity(self, limit: int = 8) -> list[tuple[str,str]]:
        with self.connect() as con: rows = con.execute("SELECT message,created_at FROM activity_log ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [(r["message"],r["created_at"]) for r in rows]

    def analytics(self) -> dict[str, Any]:
        goal = self.get_profile().career_goal
        if not goal: return {"completed":0,"total":0,"active_projects":0,"completed_projects":0,"project_total":0,"review_count":0,"skills":[],"activities":[],"reviews":[]}
        with self.connect() as con:
            completed = con.execute("SELECT COUNT(*) FROM activities WHERE career_goal=? AND status='Completed'",(goal,)).fetchone()[0]
            total = con.execute("SELECT COUNT(*) FROM activities WHERE career_goal=?",(goal,)).fetchone()[0]
            active = con.execute("SELECT COUNT(*) FROM projects WHERE category=? AND status!='Completed'",(goal,)).fetchone()[0]
            project_total = con.execute("SELECT COUNT(*) FROM projects WHERE category=?",(goal,)).fetchone()[0]
            completed_projects = con.execute("SELECT COUNT(*) FROM projects WHERE category=? AND status='Completed'",(goal,)).fetchone()[0]
            review_count = con.execute("SELECT COUNT(*) FROM reviews WHERE career_goal=?",(goal,)).fetchone()[0]
        return {"completed":completed,"total":total,"active_projects":active,"completed_projects":completed_projects,"project_total":project_total,"review_count":review_count,"skills":self.get_skills(goal),"activities":self.get_activities(goal),"reviews":self.get_reviews(goal)}
