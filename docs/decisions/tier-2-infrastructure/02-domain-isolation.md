# Domain Isolation

## Configuration Domains

Settings are grouped by domain and composed in a root `Settings` class.

```
infrastructure/configuration/
├── integrations/   (aws, google_workspace, slack, teams)
├── features/       (groups, incident)
└── infrastructure/ (server, retry, idempotency)
```

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from infrastructure.configuration.integrations import AwsSettings, SlackSettings
from infrastructure.configuration.features import GroupsFeatureSettings
from infrastructure.configuration.infrastructure import ServerSettings

class Settings(BaseSettings):
    aws: AwsSettings = AwsSettings()
    slack: SlackSettings = SlackSettings()
    groups: GroupsFeatureSettings = GroupsFeatureSettings()
    server: ServerSettings = ServerSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=True,
    )
```

**Anti-patterns**:
```python
# ❌ FORBIDDEN: Flat settings class
class Settings(BaseSettings):
    aws_region: str
    slack_token: str

# ❌ FORBIDDEN: Access without DI
settings = get_settings()
region = settings.aws.aws_region
```

Rules:
- ✅ Settings grouped by domain
- ✅ Root settings composes domains
- ✅ Access via `settings.<domain>.<field>`
- ✅ Env vars use `__` delimiter
- ❌ Never flatten settings
- ❌ Never bypass dependency injection in routes

---

## Client Facades

External service clients use facade classes with sub-clients.

```python
from typing import TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from infrastructure.configuration.integrations import GoogleWorkspaceSettings

from infrastructure.clients.google_workspace.directory import DirectoryClient
from infrastructure.clients.google_workspace.groups import GroupsClient

logger = structlog.get_logger()

class GoogleWorkspaceClients:
    def __init__(self, settings: "GoogleWorkspaceSettings") -> None:
        self.directory = DirectoryClient(settings)
        self.groups = GroupsClient(settings)
        logger.debug("google_workspace_clients_initialized")
```

**Anti-patterns**:
```python
# ❌ FORBIDDEN: Direct client use without facade
client = DirectoryClient(settings)
```

Rules:
- ✅ One facade per external service
- ✅ Facade constructs sub-clients
- ❌ Never expose raw sub-clients to application code