import sqlite3
from datetime import datetime, date

class Database:
    def __init__(self, path="feliks.db"):
        self.path = path
        self._init()

    def connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY, name TEXT, username TEXT, status TEXT DEFAULT 'Игрок')""")
            c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS applications(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, username TEXT,
                channel TEXT, subscribers TEXT, views TEXT, videos TEXT, status TEXT DEFAULT 'pending',
                created TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS questions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question TEXT, mode TEXT,
                answer TEXT, created TEXT, day TEXT)""")
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('media_open','1')")

    def ensure_user(self, uid, name, username):
        with self.connect() as c:
            c.execute("INSERT INTO users(user_id,name,username) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username", (uid,name,username or ""))

    def get_status(self, uid):
        with self.connect() as c:
            r=c.execute("SELECT status FROM users WHERE user_id=?", (uid,)).fetchone()
        return r[0] if r else "Игрок"

    def set_status(self, uid, status):
        with self.connect() as c:
            c.execute("UPDATE users SET status=? WHERE user_id=?", (status,uid))

    def is_media_open(self):
        with self.connect() as c:
            return (c.execute("SELECT value FROM settings WHERE key='media_open'").fetchone() or ["1"])[0] == "1"

    def set_media_open(self, value):
        with self.connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='media_open'", ("1" if value else "0",))

    def has_pending_application(self, uid):
        with self.connect() as c:
            return c.execute("SELECT 1 FROM applications WHERE user_id=? AND status='pending'", (uid,)).fetchone() is not None

    def create_application(self, uid, name, username, channel, subs, views, videos):
        with self.connect() as c:
            cur=c.execute("INSERT INTO applications(user_id,name,username,channel,subscribers,views,videos,created) VALUES(?,?,?,?,?,?,?,?)",
                (uid,name,username,channel,subs,views,videos,datetime.now().strftime("%Y-%m-%d %H:%M")))
            return cur.lastrowid

    def decide_application(self, app_id, status):
        with self.connect() as c:
            r=c.execute("SELECT user_id,status FROM applications WHERE id=?", (app_id,)).fetchone()
            if not r or r[1] != "pending": return None
            c.execute("UPDATE applications SET status=? WHERE id=?", (status,app_id))
            return r[0]

    def create_question(self, uid, question, mode):
        now=datetime.now()
        with self.connect() as c:
            cur=c.execute("INSERT INTO questions(user_id,question,mode,created,day) VALUES(?,?,?,?,?)",
                (uid,question,mode,now.strftime("%Y-%m-%d %H:%M"),now.strftime("%Y-%m-%d")))
            return cur.lastrowid

    def questions_today(self, uid):
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM questions WHERE user_id=? AND day=?", (uid,date.today().strftime("%Y-%m-%d"))).fetchone()[0]

    def set_ai_answer(self, qid, answer):
        with self.connect() as c:
            c.execute("UPDATE questions SET answer=? WHERE id=?", (answer,qid))

    def answer_question(self, qid, answer):
        with self.connect() as c:
            r=c.execute("SELECT user_id FROM questions WHERE id=? AND mode='admin'", (qid,)).fetchone()
            if not r: return None
            c.execute("UPDATE questions SET answer=? WHERE id=?", (answer,qid))
            return r[0]

    def user_questions(self, uid):
        with self.connect() as c:
            return c.execute("SELECT id,created,mode,question,answer FROM questions WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()

    def stats(self):
        with self.connect() as c:
            return {
                "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "apps": c.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
                "approved": c.execute("SELECT COUNT(*) FROM applications WHERE status='approved'").fetchone()[0],
                "rejected": c.execute("SELECT COUNT(*) FROM applications WHERE status='rejected'").fetchone()[0],
                "pending": c.execute("SELECT COUNT(*) FROM applications WHERE status='pending'").fetchone()[0],
                "questions": c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            }

    def recent_apps(self):
        with self.connect() as c:
            return c.execute("SELECT id,user_id,name,status,created FROM applications ORDER BY id DESC LIMIT 10").fetchall()

    def recent_questions(self):
        with self.connect() as c:
            return c.execute("SELECT id,user_id,created,question FROM questions ORDER BY id DESC LIMIT 10").fetchall()
