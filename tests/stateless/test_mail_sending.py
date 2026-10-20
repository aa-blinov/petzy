"""The letter that leaves the stand: what it says, and how it is sent (web/mail.py).

MAIL_OUTBOX=memory keeps the letters instead of sending them, so the path that talks to a
mail server never runs in the test suite. These tests cover it: the message that is handed to
the server, the way the connection is secured, the login, and the refusal to send when the
server is not configured at all
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from web import mail

BODY = "ссылка для сброса пароля"


@pytest.fixture(autouse=True)
def no_outbox(monkeypatch):
    """The letters leave the stand in these tests: the outbox is off and the server is unset."""
    monkeypatch.delenv("MAIL_OUTBOX", raising=False)
    for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def server(monkeypatch):
    """The mail server, captured: what was sent to it and how the connection was secured."""
    plain = MagicMock(name="SMTP")
    secure = MagicMock(name="SMTP_SSL")
    monkeypatch.setattr(mail.smtplib, "SMTP", plain)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", secure)
    return SimpleNamespace(
        plain=plain,
        secure=secure,
        connection=plain.return_value.__enter__.return_value,
        secure_connection=secure.return_value.__enter__.return_value,
    )


@pytest.fixture
def configured(monkeypatch):
    """A stand with a mail server behind it."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "Petzy <no-reply@example.com>")


class TestTheLetterThatIsSent:
    def test_it_carries_the_addresses_the_subject_and_the_text(self, configured, server):
        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.connection.send_message.assert_called_once()
        message = server.connection.send_message.call_args[0][0]
        assert message["From"] == "Petzy <no-reply@example.com>"
        assert message["To"] == "vera@example.com"
        assert message["Subject"] == "Сброс пароля"
        assert message.get_content().strip() == BODY
        assert message.get_content_type() == "text/plain"

    def test_the_message_id_carries_the_domain_of_the_sender(self, configured, server):
        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        message = server.connection.send_message.call_args[0][0]
        assert message["Message-ID"].endswith("@example.com>")

    def test_it_goes_to_the_configured_server(self, configured, server):
        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.plain.assert_called_once_with("smtp.example.com", 587, timeout=10)
        server.secure.assert_not_called()


class TestHowTheConnectionIsSecured:
    def test_the_plain_port_starts_tls_before_sending(self, configured, server):
        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        connection = server.connection
        connection.starttls.assert_called_once()
        assert connection.starttls.call_args.kwargs["context"] is not None

    def test_the_ssl_port_connects_with_ssl_and_does_not_start_tls(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "465")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        args, kwargs = server.secure.call_args
        assert args == ("smtp.example.com", 465)
        assert kwargs["context"] is not None
        server.plain.assert_not_called()
        server.secure_connection.starttls.assert_not_called()

    def test_the_ssl_port_sends_the_letter_too(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "465")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.secure_connection.send_message.assert_called_once()


class TestTheLogin:
    def test_no_login_without_a_user(self, configured, server):
        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.connection.login.assert_not_called()

    def test_the_login_uses_the_configured_user_and_password(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "petzy")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.connection.login.assert_called_once_with("petzy", "secret")

    def test_a_login_without_a_password_sends_an_empty_one(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "petzy")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.connection.login.assert_called_once_with("petzy", "")

    def test_the_login_also_happens_over_ssl(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USER", "petzy")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.secure_connection.login.assert_called_once_with("petzy", "secret")

    def test_a_login_without_a_password_sends_an_empty_one_over_ssl(self, configured, server, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USER", "petzy")

        mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.secure_connection.login.assert_called_once_with("petzy", "")


class TestAServerThatIsNotConfigured:
    def test_a_missing_sender_raises_instead_of_sending_nothing(self, monkeypatch, server):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

        with pytest.raises(KeyError):
            mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.plain.assert_not_called()
        server.secure.assert_not_called()

    def test_a_missing_server_raises_instead_of_sending_nothing(self, monkeypatch, server):
        monkeypatch.setenv("SMTP_FROM", "Petzy <no-reply@example.com>")

        with pytest.raises(KeyError):
            mail.send_mail("vera@example.com", "Сброс пароля", BODY)

        server.plain.assert_not_called()
        server.secure.assert_not_called()
