"""Configuration management for CronLite."""

from dataclasses import dataclass, field


@dataclass
class Config:
    """Scheduler configuration."""
    max_workers: int = 4
    db_path: str = "cronlite.db"
    tick_interval: float = 1.0  # seconds between scheduler ticks
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    log_level: str = "INFO"
    max_output_bytes: int = 10240
    default_timeout: int = 300
    default_max_retries: int = 0
    default_retry_strategy: str = "none"
    default_retry_base_delay: float = 10.0
    default_retry_max_delay: float = 300.0

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict:
        return {
            "max_workers": self.max_workers,
            "db_path": self.db_path,
            "tick_interval": self.tick_interval,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "log_level": self.log_level,
            "max_output_bytes": self.max_output_bytes,
            "default_timeout": self.default_timeout,
        }
