from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.models import WechatAccount, WechatLoginSession


def _build_channel_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    from app.wechat_channel_app import create_wechat_channel_app

    app = create_wechat_channel_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app, session


class TestChannelQrRoutes:
    """测试 wechat-channel 的二维码路由。"""

    def test_get_qr_code_returns_qr_data(self, monkeypatch):
        """/channel/qr-code 返回二维码数据。"""
        from app import wechat_channel_routes as routes_module

        monkeypatch.setattr(
            routes_module, "get_settings",
            lambda: SimpleNamespace(wechat_channel_token=None),
        )

        # Mock ILinkClient.get_qr_code
        from wechat_channel.ilink_client import ILinkClient
        original_get_qr_code = ILinkClient.get_qr_code
        monkeypatch.setattr(
            ILinkClient, "get_qr_code",
            lambda self: SimpleNamespace(qrcode_id="test_qr_001", qr_img_content="base64data"),
        )

        app, session = _build_channel_client()
        client = TestClient(app)
        response = client.get("/channel/qr-code")

        assert response.status_code == 200
        data = response.json()
        assert data["qrcode_id"] == "test_qr_001"
        assert data["qr_img_content"] == "base64data"

        # Cleanup
        monkeypatch.setattr(ILinkClient, "get_qr_code", original_get_qr_code)

    def test_get_qr_code_returns_502_on_ilink_error(self, monkeypatch):
        """/channel/qr-code 在 iLink 错误时返回 502。"""
        from app import wechat_channel_routes as routes_module

        monkeypatch.setattr(
            routes_module, "get_settings",
            lambda: SimpleNamespace(wechat_channel_token=None),
        )

        from wechat_channel.ilink_client import ILinkClient, ILinkError
        original_get_qr_code = ILinkClient.get_qr_code

        def mock_error(self):
            raise ILinkError(code=500, message="iLink 服务不可用")

        monkeypatch.setattr(ILinkClient, "get_qr_code", mock_error)

        app, session = _build_channel_client()
        client = TestClient(app)
        response = client.get("/channel/qr-code")

        assert response.status_code == 502
        assert "iLink 二维码失败" in response.text

        monkeypatch.setattr(ILinkClient, "get_qr_code", original_get_qr_code)

    def test_get_qr_code_requires_channel_token(self, monkeypatch):
        """/channel/qr-code 需要通道 token。"""
        from app import wechat_channel_routes as routes_module

        monkeypatch.setattr(
            routes_module, "get_settings",
            lambda: SimpleNamespace(wechat_channel_token="secret"),
        )
        app, session = _build_channel_client()
        client = TestClient(app)
        response = client.get("/channel/qr-code")
        assert response.status_code == 401

    def test_get_qr_code_status_returns_scanned(self, monkeypatch):
        """/channel/qr-code-status 返回 scanned 状态。"""
        from app import wechat_channel_routes as routes_module

        monkeypatch.setattr(
            routes_module, "get_settings",
            lambda: SimpleNamespace(wechat_channel_token=None),
        )

        from wechat_channel.ilink_client import ILinkClient
        original_poll = ILinkClient.poll_qr_status
        monkeypatch.setattr(
            ILinkClient, "poll_qr_status",
            lambda self, qrcode_id: SimpleNamespace(state="scanned", token=None, base_url=None),
        )

        app, session = _build_channel_client()
        client = TestClient(app)
        response = client.get("/channel/qr-code-status", params={"qrcode_id": "test_qr_001"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scanned"
        assert data["bot_token"] is None

        monkeypatch.setattr(ILinkClient, "poll_qr_status", original_poll)

    def test_get_qr_code_status_returns_confirmed_with_token(self, monkeypatch):
        """/channel/qr-code-status 返回 confirmed + bot_token。"""
        from app import wechat_channel_routes as routes_module

        monkeypatch.setattr(
            routes_module, "get_settings",
            lambda: SimpleNamespace(wechat_channel_token=None),
        )

        from wechat_channel.ilink_client import ILinkClient
        original_poll = ILinkClient.poll_qr_status
        monkeypatch.setattr(
            ILinkClient, "poll_qr_status",
            lambda self, qrcode_id: SimpleNamespace(
                state="confirmed", token="bt_real_001", base_url="https://ilink.example.com",
            ),
        )

        app, session = _build_channel_client()
        client = TestClient(app)
        response = client.get("/channel/qr-code-status", params={"qrcode_id": "test_qr_001"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["bot_token"] == "bt_real_001"
        assert data["base_url"] == "https://ilink.example.com"

        monkeypatch.setattr(ILinkClient, "poll_qr_status", original_poll)


class TestLoginAutoConfirm:
    """测试登录轮询自动确认流程。"""

    def test_poll_triggers_auto_confirm_on_confirmed(self, monkeypatch):
        """轮询 GET /me/wechat-login-sessions/{id} 时，iLink 返回 confirmed 则自动确认。"""

        # Mock channel client
        class FakeChannelClient:
            def get_channel_qr_code(self):
                return {"qr_img_content": "base64data", "qrcode_id": "qr_test_001"}
            def get_channel_qr_code_status(self, qrcode_id):
                return {
                    "status": "confirmed",
                    "bot_token": "bt_auto_001",
                    "base_url": "https://ilink.example.com",
                    "wechat_user_id": "wx_user_auto",
                }

        monkeypatch.setattr(
            "app.api.routes.wechat.build_wechat_channel_client",
            lambda: FakeChannelClient(),
        )

        # Build app
        from app.api.deps import get_db
        from app.core.config import get_settings
        from app.main import create_app
        from app.schemas.auth import LoginRequest
        from app.schemas.setup import OwnerInitRequest
        from app.services.auth_service import AuthService
        from app.services.setup_service import SetupService

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        session = SessionLocal()

        app = create_app()
        def override_get_db():
            try:
                yield session
            finally:
                pass
        app.dependency_overrides[get_db] = override_get_db

        # Seed owner + member
        settings = get_settings()
        setup = SetupService(session)
        setup.create_owner(OwnerInitRequest(
            display_name="主用户", email="owner@example.com",
        ))
        from app.services.user_service import UserService
        UserService(session).create_user(
            username="member1", password="member123", role="member",
        )
        session.commit()

        auth = AuthService(session)
        _, token, _ = auth.login(LoginRequest(username="admin", password=settings.admin_password))
        session.commit()

        client = TestClient(app)

        # Step 1: Create login session
        create_resp = client.post(
            "/api/me/wechat-login-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["data"]["login_session_id"]
        assert create_resp.json()["data"]["qr_img_content"] == "base64data"

        # Verify session has qrcode_id
        db_session = session
        login_session = db_session.query(WechatLoginSession).filter_by(
            login_session_id=session_id
        ).first()
        assert login_session is not None
        assert login_session.qrcode_id == "qr_test_001"
        assert login_session.qr_img_content == "base64data"

        # Step 2: Poll → FakeChannelClient returns confirmed → auto-confirm
        poll_resp = client.get(
            f"/api/me/wechat-login-sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()["data"]
        assert poll_data["status"] == "confirmed"
        assert poll_data["confirmed_at"] is not None

        # Verify account was created
        account = db_session.query(WechatAccount).filter_by(
            account_id="qr_test_001"
        ).first()
        assert account is not None
        assert account.bot_token == "bt_auto_001"
        assert account.base_url == "https://ilink.example.com"
        assert account.status == "active"

        # Verify identity was created
        from app.models import ChannelIdentity
        identity = db_session.query(ChannelIdentity).filter_by(
            channel_user_id="wx_user_auto"
        ).first()
        assert identity is not None
        assert identity.status == "active"

        session.close()

    def test_poll_marks_expired_on_ilink_expired(self, monkeypatch):
        """轮询时 iLink 返回 expired，session 被标记为 expired。"""


        class FakeChannelClient:
            def get_channel_qr_code(self):
                return {"qr_img_content": "base64data", "qrcode_id": "qr_exp_test"}
            def get_channel_qr_code_status(self, qrcode_id):
                return {"status": "expired", "bot_token": None, "base_url": None}

        monkeypatch.setattr(
            "app.api.routes.wechat.build_wechat_channel_client",
            lambda: FakeChannelClient(),
        )

        from app.api.deps import get_db
        from app.core.config import get_settings
        from app.main import create_app
        from app.schemas.auth import LoginRequest
        from app.schemas.setup import OwnerInitRequest
        from app.services.auth_service import AuthService
        from app.services.setup_service import SetupService

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        session = SessionLocal()

        app = create_app()
        def override_get_db():
            try:
                yield session
            finally:
                pass
        app.dependency_overrides[get_db] = override_get_db

        settings = get_settings()
        setup = SetupService(session)
        setup.create_owner(OwnerInitRequest(
            display_name="主用户", email="owner@example.com",
        ))
        session.commit()

        auth = AuthService(session)
        _, token, _ = auth.login(LoginRequest(username="admin", password=settings.admin_password))
        session.commit()

        client = TestClient(app)

        create_resp = client.post(
            "/api/me/wechat-login-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["data"]["login_session_id"]

        poll_resp = client.get(
            f"/api/me/wechat-login-sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()["data"]
        assert poll_data["status"] == "expired"

        session.close()
