from app.extensions import db


class MastCategory(db.Model):
    __tablename__ = "Mast_Categories"

    Id_Cat = db.Column(db.Integer, primary_key=True)

    Cat_Desc = db.Column(
        db.String(50),
        nullable=False,
        unique=True
    )

    def __repr__(self):
        return f"<MastCategory {self.Cat_Desc}>"
