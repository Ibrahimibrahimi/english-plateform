import os

from app.main import app

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "1942")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
    )
