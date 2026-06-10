from app.db.session import SessionLocal
from app.services.wechat_channel_service import WechatChannelService

long_msg = (
    "测试长消息 - 以下是测试内容\n\n"
    "如果收到这条长消息请回复2\n"
    "收不到这条但收到上一条短消息请回复3\n\n"
    "测试日程列表：\n"
    "  - 09:00 测试第一行\n"
    "  - 10:00 测试第二行\n"
    "  - 11:00 测试第三行\n"
    "  - 12:00 测试第四行\n"
    "  - 13:00 测试第五行\n"
    "  - 14:00 测试第六行\n"
    "  - 15:00 测试第七行\n"
    "  - 16:00 测试第八行\n"
)

db = SessionLocal()
svc = WechatChannelService(db)
log = svc.send_text(
    conversation_id="o9cq80-5dawlr40EUeiNgD2lNC1s@im.wechat",
    content=long_msg,
    user_id="465336f6-5fc3-4ea4-bdc8-8cbf8eb04311",
)
print(f"status={log.status} error={log.error_code} {log.error_message}")
db.commit()
db.close()
