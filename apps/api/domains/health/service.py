from domains.health.schema import HealthStatus


class HealthService:
    def check(self) -> HealthStatus:
        return HealthStatus()
