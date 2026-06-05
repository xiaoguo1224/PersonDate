from app.db.session import SessionLocal
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService


def bootstrap_owner() -> None:
    with SessionLocal() as db:
        service = SetupService(db)
        if service.is_initialized():
            return
        service.create_owner(OwnerInitRequest(display_name="系统主用户"))
        db.commit()


if __name__ == "__main__":
    bootstrap_owner()
