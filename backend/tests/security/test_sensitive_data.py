from app.security.constants import ModerationAction
from app.security.content_moderator import content_moderator


def test_personal_data_is_masked_before_downstream_processing() -> None:
    raw = "姓名张三，手机号13812345678，邮箱zhangsan@example.com，工号EMP-001。"
    result = content_moderator.moderate(raw)

    assert result.action == ModerationAction.MASK
    assert "13812345678" not in (result.masked_text or "")
    assert "zhangsan@example.com" not in (result.masked_text or "")
    assert "EMP-001" not in (result.masked_text or "")
    assert {"mobile", "email", "employee_id"}.issubset(set(result.sensitive_types))


def test_credentials_are_redacted_and_blocked() -> None:
    samples = [
        "RAG接口密钥是sk-test-1234567890，请验证。",
        "数据库地址mysql://root:Secret123@10.0.0.8:3306/ops，帮我排查。",
        "登录账号admin，密码Aoc@Test2026，请直接帮我登录。",
    ]
    for raw in samples:
        result = content_moderator.moderate(raw)
        assert result.action == ModerationAction.BLOCK
        assert "Secret123" not in (result.masked_text or "")
        assert "sk-test-1234567890" not in (result.masked_text or "")
        assert "Aoc@Test2026" not in (result.masked_text or "")


def test_sensitive_output_is_never_echoed_verbatim() -> None:
    result = content_moderator.moderate_output("联系人邮箱zhangsan@example.com")
    assert result.action == ModerationAction.MASK
    assert "zhangsan@example.com" not in (result.masked_text or "")
