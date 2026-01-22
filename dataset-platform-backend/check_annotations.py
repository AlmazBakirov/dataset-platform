from app.db.session import SessionLocal
from app.models.annotation import Annotation


db = SessionLocal()
try:
    rows = db.query(Annotation).order_by(Annotation.id.desc()).limit(20).all()
    print("rows:", len(rows))
    for r in rows:
        print(r.id, r.task_id, r.image_id, r.labeler_id, r.labels, r.updated_at)
finally:
    db.close()
