import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import random
import sqlite3
import os
from datetime import datetime

DB_NAME = "quiz_game.db"
SEED_FILE = "questions.json"


# ---------- DATABASE LAYER ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            option1 TEXT NOT NULL,
            option2 TEXT NOT NULL,
            option3 TEXT NOT NULL,
            option4 TEXT NOT NULL,
            answer INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM questions")
    if cur.fetchone()[0] == 0 and os.path.exists(SEED_FILE):
        try:
            with open(SEED_FILE, "r") as f:
                data = json.load(f)
            for q in data:
                cur.execute("""
                    INSERT INTO questions (topic, question, option1, option2, option3, option4, answer)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (q["topic"], q["question"], q["options"][0], q["options"][1],
                      q["options"][2], q["options"][3], q["answer"]))
            conn.commit()
        except Exception as e:
            print("Seed error:", e)
    conn.close()


def get_topics():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT topic FROM questions ORDER BY topic")
    topics = [row[0] for row in cur.fetchall()]
    conn.close()
    return topics


def get_questions(topic="All"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if topic == "All":
        cur.execute("SELECT * FROM questions")
    else:
        cur.execute("SELECT * FROM questions WHERE topic = ?", (topic,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "topic": r[1], "question": r[2],
         "options": [r[3], r[4], r[5], r[6]], "answer": r[7]}
        for r in rows
    ]


def add_question(topic, question, options, answer):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO questions (topic, question, option1, option2, option3, option4, answer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (topic, question, options[0], options[1], options[2], options[3], answer))
    conn.commit()
    conn.close()


def delete_question(qid):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()


def save_score(username, topic, difficulty, score, total):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("""
        INSERT INTO scores (username, topic, difficulty, score, total, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, topic, difficulty, score, total, ts))
    conn.commit()
    conn.close()


def get_user_scores(username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT topic, difficulty, score, total, timestamp
        FROM scores WHERE username = ?
        ORDER BY id DESC
    """, (username,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_stats(username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), MAX(score * 100.0 / total),
               AVG(score * 100.0 / total)
        FROM scores WHERE username = ?
    """, (username,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return {"quizzes": row[0],
                "best": round(row[1], 1),
                "average": round(row[2], 1)}
    return {"quizzes": 0, "best": 0, "average": 0}


# ---------- GUI ----------
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Game – Week 4")
        self.root.geometry("680x600")
        self.root.configure(bg="#f0f4f8")

        self.username = None
        self.selected_questions = []
        self.current_q_index = 0
        self.score = 0
        self.time_left = 0
        self.timer_id = None
        self.answered = False
        self.difficulty = "Medium"
        self.current_topic = "All"

        self.ask_username()

    def ask_username(self):
        name = simpledialog.askstring("Login", "Enter your name:", parent=self.root)
        if not name or not name.strip():
            name = "Guest"
        self.username = name.strip()
        self.show_main_menu()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()
        if self.timer_id:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None

    def show_main_menu(self):
        self.clear()
        tk.Label(self.root, text="🎮 Quiz Game", font=("Arial", 24, "bold"),
                 bg="#f0f4f8", fg="#1a3c6e").pack(pady=15)
        tk.Label(self.root, text=f"👤 User: {self.username}",
                 font=("Arial", 12, "italic"), bg="#f0f4f8", fg="#555").pack()

        tk.Label(self.root, text="Select Topic:", font=("Arial", 13),
                 bg="#f0f4f8").pack(pady=(15, 2))
        topics = ["All"] + get_topics()
        self.topic_var = tk.StringVar(value="All")
        tk.OptionMenu(self.root, self.topic_var, *topics).pack()

        tk.Label(self.root, text="Select Difficulty:", font=("Arial", 13),
                 bg="#f0f4f8").pack(pady=(15, 2))
        self.diff_var = tk.StringVar(value="Medium")
        tk.OptionMenu(self.root, self.diff_var, "Easy", "Medium", "Hard").pack()

        tk.Button(self.root, text="▶  Start Quiz", font=("Arial", 13, "bold"),
                  bg="#4CAF50", fg="white", width=20, height=2,
                  command=self.start_quiz).pack(pady=18)
        tk.Button(self.root, text="📊  My Score History", font=("Arial", 11),
                  bg="#2196F3", fg="white", width=20,
                  command=self.show_history).pack(pady=4)
        tk.Button(self.root, text="📈  My Statistics", font=("Arial", 11),
                  bg="#9C27B0", fg="white", width=20,
                  command=self.show_stats).pack(pady=4)
        tk.Button(self.root, text="🛠  Admin – Manage Questions", font=("Arial", 11),
                  bg="#FF9800", fg="white", width=20,
                  command=self.admin_panel).pack(pady=4)
        tk.Button(self.root, text="🚪  Exit", font=("Arial", 11),
                  bg="#d32f2f", fg="white", width=20,
                  command=self.root.quit).pack(pady=10)

    def start_quiz(self):
        self.current_topic = self.topic_var.get()
        self.difficulty = self.diff_var.get()
        self.selected_questions = get_questions(self.current_topic)
        if not self.selected_questions:
            messagebox.showerror("Error", "No questions for that topic.")
            return
        random.shuffle(self.selected_questions)
        self.current_q_index = 0
        self.score = 0
        self.show_question()

    def get_time_limit(self):
        return {"Easy": 30, "Medium": 20, "Hard": 10}.get(self.difficulty, 20)

    def show_question(self):
        self.clear()
        self.answered = False
        if self.current_q_index >= len(self.selected_questions):
            self.show_result()
            return

        q = self.selected_questions[self.current_q_index]
        self.time_left = self.get_time_limit()

        top = tk.Frame(self.root, bg="#f0f4f8")
        top.pack(fill="x", pady=8)
        tk.Label(top, text=f"Q {self.current_q_index + 1}/{len(self.selected_questions)}",
                 font=("Arial", 11), bg="#f0f4f8").pack(side="left", padx=15)
        tk.Label(top, text=f"Score: {self.score}",
                 font=("Arial", 11, "bold"), bg="#f0f4f8",
                 fg="#1a3c6e").pack(side="right", padx=15)

        self.timer_lbl = tk.Label(self.root, text=f"⏱ {self.time_left}s",
                                   font=("Arial", 15, "bold"),
                                   bg="#f0f4f8", fg="#d32f2f")
        self.timer_lbl.pack(pady=4)

        tk.Label(self.root, text=q["question"], font=("Arial", 15, "bold"),
                 bg="#f0f4f8", wraplength=580, justify="center").pack(pady=20)

        for i, opt in enumerate(q["options"]):
            tk.Button(self.root, text=f"{i+1}.  {opt}", font=("Arial", 12),
                      width=42, bg="white", activebackground="#bbdefb",
                      command=lambda idx=i: self.check_answer(idx)).pack(pady=5)

        self.tick()

    def tick(self):
        if self.answered:
            return
        if self.time_left > 0:
            self.timer_lbl.config(text=f"⏱ {self.time_left}s")
            self.time_left -= 1
            self.timer_id = self.root.after(1000, self.tick)
        else:
            self.check_answer(-1)

    def check_answer(self, idx):
        if self.answered:
            return
        self.answered = True
        if self.timer_id:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None

        q = self.selected_questions[self.current_q_index]
        if idx == -1:
            messagebox.showinfo("Time's Up",
                f"⏰ Time's up!\nCorrect answer: {q['options'][q['answer']]}")
        elif idx == q["answer"]:
            self.score += 1
            messagebox.showinfo("Correct", "✅ Correct!")
        else:
            messagebox.showinfo("Wrong",
                f"❌ Wrong!\nCorrect answer: {q['options'][q['answer']]}")

        self.current_q_index += 1
        self.show_question()

    def show_result(self):
        self.clear()
        total = len(self.selected_questions)
        pct = (self.score / total) * 100
        save_score(self.username, self.current_topic,
                   self.difficulty, self.score, total)

        tk.Label(self.root, text="🎉 Quiz Complete!", font=("Arial", 24, "bold"),
                 bg="#f0f4f8", fg="#1a3c6e").pack(pady=25)
        tk.Label(self.root, text=f"Score: {self.score}/{total}",
                 font=("Arial", 18), bg="#f0f4f8").pack()
        tk.Label(self.root, text=f"{pct:.1f}%", font=("Arial", 22, "bold"),
                 bg="#f0f4f8", fg="#4CAF50").pack(pady=8)

        msg = "🌟 Perfect!" if pct == 100 else (
              "👍 Great job!" if pct >= 70 else "📚 Keep practicing!")
        tk.Label(self.root, text=msg, font=("Arial", 13, "italic"),
                 bg="#f0f4f8", fg="#555").pack(pady=10)

        tk.Button(self.root, text="🔁 Play Again", font=("Arial", 13, "bold"),
                  bg="#4CAF50", fg="white", width=18, height=2,
                  command=self.show_main_menu).pack(pady=15)

    def show_history(self):
        rows = get_user_scores(self.username)
        win = tk.Toplevel(self.root)
        win.title(f"History – {self.username}")
        win.geometry("600x420")
        win.configure(bg="#f0f4f8")
        tk.Label(win, text=f"📊 History for {self.username}",
                 font=("Arial", 16, "bold"), bg="#f0f4f8").pack(pady=10)
        if not rows:
            tk.Label(win, text="No quizzes yet.", font=("Arial", 12),
                     bg="#f0f4f8").pack(pady=20)
        else:
            txt = tk.Text(win, width=72, height=18, font=("Courier", 10))
            txt.pack(padx=12, pady=8)
            txt.insert(tk.END, f"{'Topic':<12}{'Diff':<10}{'Score':<10}{'When'}\n")
            txt.insert(tk.END, "-" * 70 + "\n")
            for t, d, s, tt, ts in rows:
                txt.insert(tk.END, f"{t:<12}{d:<10}{s}/{tt:<7}{ts}\n")
            txt.config(state="disabled")

    def show_stats(self):
        st = get_user_stats(self.username)
        win = tk.Toplevel(self.root)
        win.title("My Stats")
        win.geometry("360x260")
        win.configure(bg="#f0f4f8")
        tk.Label(win, text=f"📈 Stats for {self.username}",
                 font=("Arial", 16, "bold"), bg="#f0f4f8").pack(pady=15)
        tk.Label(win, text=f"Quizzes taken:  {st['quizzes']}",
                 font=("Arial", 13), bg="#f0f4f8").pack(pady=5)
        tk.Label(win, text=f"Best score:  {st['best']}%",
                 font=("Arial", 13), bg="#f0f4f8", fg="#4CAF50").pack(pady=5)
        tk.Label(win, text=f"Average score:  {st['average']}%",
                 font=("Arial", 13), bg="#f0f4f8", fg="#2196F3").pack(pady=5)

    def admin_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Admin – Manage Questions")
        win.geometry("620x520")
        win.configure(bg="#f0f4f8")

        tk.Label(win, text="🛠 Question Manager",
                 font=("Arial", 16, "bold"), bg="#f0f4f8").pack(pady=10)

        listbox = tk.Listbox(win, width=85, height=16, font=("Courier", 9))
        listbox.pack(padx=10, pady=5)

        def refresh():
            listbox.delete(0, tk.END)
            for q in get_questions("All"):
                listbox.insert(tk.END,
                    f"[{q['id']}] ({q['topic']}) {q['question'][:60]}")

        def delete_selected():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("Info", "Select a question to delete.")
                return
            text = listbox.get(sel[0])
            qid = int(text.split("]")[0].strip("["))
            if messagebox.askyesno("Confirm", "Delete this question?"):
                delete_question(qid)
                refresh()

        def add_new():
            top = tk.Toplevel(win)
            top.title("Add Question")
            top.geometry("520x420")
            top.configure(bg="#f0f4f8")

            fields = ["Topic", "Question", "Option 1", "Option 2",
                      "Option 3", "Option 4", "Correct (1-4)"]
            entries = []
            for f in fields:
                tk.Label(top, text=f, font=("Arial", 11),
                         bg="#f0f4f8", anchor="w").pack(fill="x", padx=15, pady=2)
                e = tk.Entry(top, width=55)
                e.pack(padx=15, pady=2)
                entries.append(e)

            def save():
                vals = [e.get().strip() for e in entries]
                if not all(vals):
                    messagebox.showerror("Error", "Fill all fields.")
                    return
                try:
                    ans = int(vals[6]) - 1
                    if not (0 <= ans <= 3):
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "Answer must be 1-4.")
                    return
                add_question(vals[0], vals[1], vals[2:6], ans)
                messagebox.showinfo("Saved", "Question added!")
                top.destroy()
                refresh()

            tk.Button(top, text="Save", font=("Arial", 12, "bold"),
                      bg="#4CAF50", fg="white", width=15,
                      command=save).pack(pady=12)

        tk.Button(win, text="➕ Add Question", font=("Arial", 11),
                  bg="#4CAF50", fg="white", width=18,
                  command=add_new).pack(side="left", padx=20, pady=10)
        tk.Button(win, text="🗑 Delete Selected", font=("Arial", 11),
                  bg="#d32f2f", fg="white", width=18,
                  command=delete_selected).pack(side="left", padx=20, pady=10)
        tk.Button(win, text="🔄 Refresh", font=("Arial", 11),
                  bg="#2196F3", fg="white", width=18,
                  command=refresh).pack(side="left", padx=20, pady=10)

        refresh()


if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()