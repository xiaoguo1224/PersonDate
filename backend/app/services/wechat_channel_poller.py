from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.schemas.wechat import WechatInboundRequest
from app.services.wechat_channel_adapter import WechatChannelAdapter
from app.services.wechat_channel_service import WechatChannelService


@dataclass(slots=True)
class WechatPollMessage:
    message_id: str | None
    conversation_id: str
    channel_user_id: str
    display_name: str | None
    context_token: str | None
    content_type: str
    content: str
    raw_payload: dict[str, Any]


@dataclass(slots=True)
class WechatPollResult:
    messages: list[WechatPollMessage]
    next_cursor: str | None


class WechatUpdatesClient(Protocol):
    def get_updates(self, *, bot_token: str, cursor: str | None = None) -> Any:
        ...


class WechatChannelPoller:
    def __init__(
        self,
        db: Session,
        updates_client: WechatUpdatesClient,
        adapter: WechatChannelAdapter | None = None,
    ) -> None:
        self.db = db
        self.updates_client = updates_client
        self.adapter = adapter or WechatChannelAdapter(db)

    def poll_account_once(self, account_id: str) -> int:
        service = WechatChannelService(self.db)
        account = service.get_account_by_account_id(account_id)
        if account is None or account.status != "active":
            return 0

        try:
            result = self._normalize_updates(
                self.updates_client.get_updates(bot_token=account.bot_token, cursor=account.cursor)
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                service.update_account_status(
                    account_id=account.account_id,
                    status="expired",
                    last_active_time=datetime.now(UTC),
                )
                self.db.commit()
                return 0
            service.update_account_status(
                account_id=account.account_id,
                status="error",
                last_active_time=datetime.now(UTC),
            )
            self.db.commit()
            raise
        except httpx.RequestError:
            service.update_account_status(
                account_id=account.account_id,
                status="error",
                last_active_time=datetime.now(UTC),
            )
            self.db.commit()
            raise

        processed_count = 0
        for message in result.messages:
            inbound_request = WechatInboundRequest(
                message_id=message.message_id,
                account_id=account.account_id,
                conversation_id=message.conversation_id,
                channel_user_id=message.channel_user_id,
                display_name=message.display_name,
                context_token=message.context_token,
                content_type=message.content_type,
                content=message.content,
                raw_payload=message.raw_payload,
            )
            handling = self.adapter.handle_inbound_message(
                inbound_request,
                channel_token=None,
                require_auth=False,
            )
            if handling.response.handled:
                processed_count += 1
                reply = handling.response.reply
                if reply and message.context_token:
                    try:
                        service.send_text(
                            conversation_id=message.conversation_id,
                            content=reply,
                            context_token=message.context_token,
                            user_id=None,
                            channel_user_id=message.channel_user_id,
                        )
                        self.db.commit()
                    except Exception:
                        self.db.rollback()

        service.update_account_cursor(
            account_id=account.account_id,
            cursor=result.next_cursor,
            last_active_time=datetime.now(UTC),
        )
        self.db.commit()
        return processed_count

    def poll_active_accounts_once(self) -> int:
        total_processed = 0
        service = WechatChannelService(self.db)
        for account in service.list_active_accounts():
            total_processed += self.poll_account_once(account.account_id)
        return total_processed

    def _normalize_updates(self, payload: Any) -> WechatPollResult:
        if isinstance(payload, dict):
            raw_messages = payload.get("messages") or payload.get("msgs") or []
            next_cursor = payload.get("get_updates_buf") or payload.get("cursor")
        else:
            raw_messages = getattr(payload, "messages", None) or getattr(
                payload,
                "msgs",
                None,
            ) or []
            next_cursor = getattr(payload, "next_cursor", None) or getattr(
                payload,
                "get_updates_buf",
                None,
            ) or getattr(
                payload,
                "cursor",
                None,
            )

        messages = [self._normalize_message(item) for item in raw_messages]
        return WechatPollResult(messages=messages, next_cursor=next_cursor)

    def _normalize_message(self, item: Any) -> WechatPollMessage:
        if isinstance(item, dict):
            raw_payload = item
            message_id = item.get("message_id") or item.get("msg_id") or item.get("id")
            conversation_id = (
                item.get("conversation_id")
                or item.get("session_id")
                or item.get("to_user_id")
                or item.get("from_user_id")
                or ""
            )
            channel_user_id = (
                item.get("channel_user_id")
                or item.get("from_user_id")
                or conversation_id
            )
            display_name = item.get("display_name")
            context_token = item.get("context_token")
            content_type = item.get("content_type") or item.get("message_type") or "text"
            content = item.get("content") or item.get("text") or ""
        else:
            raw_payload = item.model_dump() if hasattr(item, "model_dump") else {"value": str(item)}
            message_id = getattr(item, "message_id", None) or getattr(item, "msg_id", None)
            conversation_id = (
                getattr(item, "conversation_id", None)
                or getattr(item, "session_id", None)
                or getattr(item, "to_user_id", None)
                or getattr(item, "from_user_id", None)
                or ""
            )
            channel_user_id = (
                getattr(item, "channel_user_id", None)
                or getattr(item, "from_user_id", None)
                or conversation_id
            )
            display_name = getattr(item, "display_name", None)
            context_token = getattr(item, "context_token", None)
            content_type = (
                getattr(item, "content_type", None)
                or getattr(item, "message_type", None)
                or "text"
            )
            content = getattr(item, "content", None) or getattr(item, "text", None) or ""

        return WechatPollMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            channel_user_id=channel_user_id,
            display_name=display_name,
            context_token=context_token,
            content_type=content_type,
            content=content,
            raw_payload=raw_payload,
        )
