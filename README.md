# SkillBridge AI

SkillBridge AI is a PyQt6 career learning app. It saves the student's profile, self-assessments, Gemini recommendations, learning activities, projects, portfolio reviews, and progress in SQLite.

## Run

1. Install Python 3.11 or newer.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python main.py`.

On first launch, enter your name, education, any career title, experience level, and existing skills. Career suggestions are searchable, and custom careers are accepted. Your selected career is shared by all career pages.

## Gemini behavior

All career descriptions, skill-gap guidance, roadmaps, project ideas, career comparisons, and image reviews come from the configured Gemini API. The app does not seed sample profiles or substitute canned recommendations. On first setup, enter a Gemini API key once and choose **Save securely and test connection**. SkillBridge stores it in the operating system credential store and reads it automatically on later launches. The key is masked while entering and is never shown in the UI or application logs.

You can instead set `GEMINI_API_KEY` or `GOOGLE_API_KEY` in your environment or in a private `.env` file beside `main.py`. The app loads that project `.env` regardless of the current launch directory. If both variables are set, `GOOGLE_API_KEY` takes precedence. When no credential is available, Gemini setup explains that authentication is required and AI actions remain disabled. The **Test Gemini connection** button makes a real API request. Network, quota, credential, and invalid-response errors are shown without exposing the key.

The generated roadmap and recommendations are stored in SQLite. Completing an activity or project changes saved progress. New roadmap suggestions use current profile data, skill assessments, completed projects, and saved portfolio feedback. Uploaded images are sent to Gemini only when the student starts a portfolio review.

## Local data

The database is created at `data/skillbridge.sqlite3`. Set `SKILLBRIDGE_DB_PATH` to use another location. Keep `.env` private; it contains the API key. The repository ignores `.env` files and local database contents.
