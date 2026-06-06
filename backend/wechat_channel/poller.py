# backend/wechat_channel/poller.py
from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import WechatChannelInboundMessage
from wechat_channel.ilink_client import ILinkClient, ILinkSessionExpired

logger = logging.getLogger(__name__)


@dataclass
class PollerThread(threading.Thread):
    """单个微信账号的长轮询拉取线程。"""

    account_id: str
    bot_token: str
    cursor: str | None
    db_url: str
    ilink: ILinkClient = field(default_factory=ILinkClient)
    running: bool = True
    daemon: bool = True

    def __post_init__(self) -> None:
        super().__init__(name=f"poller-{self.account_id[:8]}", daemon=True)
        engine = create_engine(self.db_url)
        self._session_factory = sessionmaker(bind=engine)

    def run(self) -> None:
        logger.info("Poller 启动: account=%s", self.account_id)
        consecutive_errors = 0

        while self.running:
            try:
                result = self.ilink.get_updates(
                    bot_token=self.bot_token,
                    cursor=self.cursor,
                )
                consecutive_errors = 0

                if result.msgs:
                    self._process_messages(result.msgs)

                if result.new_cursor != self.cursor:
                    self.cursor = result.new_cursor
                    self._save_cursor()

            except ILinkSessionExpired:
                logger.warning("Session 过期: account=%s", self.account_id)
                self._mark_expired()
                break
            except Exception:
                consecutive_errors += 1
                wait = min(consecutive_errors * 2, 30)
                logger.exception(
                    "Poller 异常(account=%s, retry=%ds)", self.account_id, wait
                )
                time.sleep(wait)

    def _process_messages(self, msgs: list[dict[str, Any]]) -> None:
        db = self._session_factory()
        try:
            for msg in msgs:
                if msg.get("message_type") != 1:
                    continue
                text = (
                    msg.get("item_list", [{}])[0]
                    .get("text_item", {})
                    .get("text", "")
                )
                if not text:
                    continue

                from_user = msg.get("from_user_id", "")
                context_token = msg.get("context_token")
                msg_id = msg.get("msg_id") or f"{from_user}_{int(datetime.now(UTC).timestamp())}"

                existing = db.query(WechatChannelInboundMessage).filter(
                    WechatChannelInboundMessage.account_id == self.account_id,
                    WechatChannelInboundMessage.message_id == msg_id,
                ).first()
                if existing:
                    continue

                inbound = WechatChannelInboundMessage(
                    account_id=self.account_id,
                    message_id=msg_id,
                    cursor_token=self._build_cursor_token(),
                    conversation_id=from_user,
                    channel_user_id=from_user,
                    content_type="text",
                    content=text,
                    context_token=context_token,
                    raw_payload=msg,
                    status="pending",
                )
                db.add(inbound)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("消息处理失败: account=%s", self.account_id)
        finally:
            db.close()

    def _save_cursor(self) -> None:
        db = self._session_factory()
        try:
            from app.models import WechatAccount
            account = db.query(WechatAccount).filter(
                WechatAccount.account_id == self.account_id
            ).first()
            if account:
                account.cursor = self.cursor
                account.last_active_time = datetime.now(UTC)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("游标保存失败: account=%s", self.account_id)
        finally:
            db.close()

    def _mark_expired(self) -> None:
        db = self._session_factory()
        try:
            from app.models import WechatAccount
            account = db.query(WechatAccount).filter(
                WechatAccount.account_id == self.account_id
            ).first()
            if account:
                account.status = "expired"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def stop(self) -> None:
        self.running = False

    @staticmethod
    def _build_cursor_token() -> str:
        timestamp = int(datetime.now(UTC).timestamp() * 1000)
        return f"{timestamp:013d}_{secrets.token_hex(8)}"


@dataclass
class PollerManager:
    """管理所有账号的 PollerThread 生命周期。"""

    db_url: str

    def __post_init__(self) -> None:
        self._threads: dict[str, PollerThread] = {}

    def start_all(self, accounts: list[tuple[str, str, str | None]]) -> None:
        for account_id, bot_token, cursor in accounts:
            if account_id in self._threads:
                continue
            thread = PollerThread(
                account_id=account_id,
                bot_token=bot_token,
                cursor=cursor,
                db_url=self.db_url,
            )
            thread.start()
            self._threads[account_id] = thread
            logger.info("Poller 已启动: %s", account_id)

    def stop_all(self) -> None:
        for thread in self._threads.values():
            thread.stop()
        for thread in self._threads.values():
            thread.join(timeout=5)
        self._threads.clear()

    def refresh(self, accounts: list[tuple[str, str, str | None]]) -> None:
        active_ids = {a[0] for a in accounts}
        for account_id in list(self._threads.keys()):
            if account_id not in active_ids:
                self._threads[account_id].stop()
                del self._threads[account_id]
        self.start_all(accounts)
