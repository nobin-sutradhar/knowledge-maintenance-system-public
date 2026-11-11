from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

APP_DIR = Path(__file__).resolve().parent.parent
DB_PATH = APP_DIR / "knowledge.db"
CONFIG_PATH = APP_DIR / "config.toml"

DEFAULTS = {
    "daily_limit": 2,
    "default_review_days": 0,
    "correct_review_days": 7,
    "partial_review_days": 3,
    "wrong_review_days": 1,
    "dont_know_review_days": 0,
    "review_mode": "recall",
}
VALID_MODES = {"recall", "explain", "apply"}

def load_config():
    config = DEFAULTS.copy()
    if not CONFIG_PATH.exists() or tomllib is None:
        return config
    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
        review = data.get("review", {})
        for key, default in DEFAULTS.items():
            if key == "review_mode":
                value = str(review.get(key, default)).lower()
                config[key] = value if value in VALID_MODES else default
            else:
                config[key] = max(0, int(review.get(key, default)))
    except (OSError, ValueError, TypeError):
        pass
    return config
