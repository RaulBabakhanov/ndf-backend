from app.core import config as config_module


def test_database_url_defaults_to_localhost_for_local_runs(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config_module, "is_running_in_container", lambda: False)

    settings = config_module.Settings()

    assert settings.database_url == "postgresql+asyncpg://ndf_user:ndf_password@localhost:5433/ndf-database"


def test_database_url_defaults_to_container_host_when_running_in_docker(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config_module, "is_running_in_container", lambda: True)

    settings = config_module.Settings()

    assert settings.database_url == "postgresql+asyncpg://ndf_user:ndf_password@database:5432/ndf-database"
