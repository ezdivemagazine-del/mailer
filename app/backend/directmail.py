"""
阿里雲 DirectMail 發送模組（暫時停用，ARM32 相容性問題）
"""

try:
    from alibabacloud_dm20151123.client import Client
    from alibabacloud_dm20151123.models import SingleSendMailRequest
    from alibabacloud_tea_openapi.models import Config
    _DIRECTMAIL_AVAILABLE = True
except ImportError:
    _DIRECTMAIL_AVAILABLE = False


def _make_client(access_key_id: str, access_key_secret: str):
    config = Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint="dm.aliyuncs.com",
    )
    return Client(config)


def test_directmail(access_key_id: str, access_key_secret: str, from_addr: str) -> tuple[bool, str]:
    if not _DIRECTMAIL_AVAILABLE:
        return False, "DirectMail 模組尚未安裝，請聯絡管理員"
    try:
        client = _make_client(access_key_id, access_key_secret)
        req = SingleSendMailRequest(
            account_name=from_addr,
            address_type=1,
            reply_to_address=False,
            to_address=from_addr,
            subject="【易潛企業開發信系統】DirectMail 連線測試",
            text_body="此為系統自動發出的連線測試信，代表 DirectMail 設定正確。",
        )
        client.single_send_mail(req)
        return True, "連線測試成功，測試信已寄出"
    except Exception as e:
        msg = str(e)
        if "InvalidAccessKeyId" in msg:
            return False, "AccessKey ID 無效，請確認"
        if "SignatureDoesNotMatch" in msg:
            return False, "AccessKey Secret 錯誤"
        if "InvalidFromAccount" in msg or "NotExist" in msg:
            return False, "發信地址未在 DirectMail 後台驗證，請先完成域名驗證"
        return False, msg


def send_one_directmail(access_key_id: str, access_key_secret: str,
                        from_addr: str, to_addr: str,
                        subject: str, body: str) -> tuple[bool, str]:
    if not _DIRECTMAIL_AVAILABLE:
        return False, "DirectMail 模組尚未安裝"
    try:
        client = _make_client(access_key_id, access_key_secret)
        req = SingleSendMailRequest(
            account_name=from_addr,
            address_type=1,
            reply_to_address=False,
            to_address=to_addr,
            subject=subject,
            text_body=body,
        )
        client.single_send_mail(req)
        return True, ""
    except Exception as e:
        return False, str(e)
