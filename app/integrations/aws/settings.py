"""AWS vendor settings slice: the [aws] table of the configuration files.

Exposes `AWSSettings`, its tenant entry `AwsTenant`, and the cached `get_aws_settings()`
provider, read by the client factory, the error classifier in `integrations.aws.client`
and the AWS platform adapters.

[aws] holds only the client tuning (retry policy, per-attempt timeouts, boto3 error-code
catalogues), shared with hosting, which reaches DynamoDB through the same factory with no
tenant. The managed AWS organisation is the optional tenant entry, read only from the
environment as AWS__TENANT__<FIELD>: the Identity Center identity store id and instance ARN
are internal tenant identifiers only Identity Center administrators see (the id is also the
default access-portal subdomain), so they are non-public values (decisions/configuration.md)
and no configuration file names the entry. It is present when AWS__TENANT__INSTANCE_ID is
set and then needs AWS__TENANT__INSTANCE_ARN, each checked against the format AWS
documents; the audit, org and logging role ARNs and the DevOps Agent investigation role ARN
are individually optional, and an empty value counts as unset. An absent tenant keeps the bot's own credentials and empty instance
values. The region and the dynamodb-local endpoint are the SDK's: boto3 resolves them from
AWS_DEFAULT_REGION or the shared config file and AWS_ENDPOINT_URL_DYNAMODB, so no field
declares them. The two SSO permission sets are access policy and live in
`packages.access.common.settings`.
"""

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice

# The tenant entry's fields, read from the environment as AWS__TENANT__<FIELD>; empty counts as unset.
_TENANT_FIELDS = (
    "instance_id",
    "instance_arn",
    "audit_role_arn",
    "org_role_arn",
    "logging_role_arn",
    "devops_agent_role_arn",
)
_TENANT_VARIABLE = "AWS__TENANT__{}"

RetryMode = Literal["legacy", "standard", "adaptive"]

# IdentityStoreId: "d-" and ten hex digits, or a UUID
# (https://docs.aws.amazon.com/singlesignon/latest/IdentityStoreAPIReference/API_ListUsers.html).
_IDENTITY_STORE_ID = r"^(d-[0-9a-f]{10}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
# InstanceArn (https://docs.aws.amazon.com/singlesignon/latest/APIReference/API_ListAccountAssignments.html).
_INSTANCE_ARN = r"^arn:aws(-[a-z]{1,5}){0,3}:sso:::instance/(sso)?ins-[a-zA-Z0-9-.]{16}$"


class AwsTenant(BaseModel):
    """The AWS organisation this instance manages: its Identity Center instance and the roles it assumes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instance_id: str = Field(
        pattern=_IDENTITY_STORE_ID,
        description="Identity Center identity store id (d-xxxxxxxxxx), the AWS tenant id every Identity Store call carries.",
    )
    instance_arn: str = Field(pattern=_INSTANCE_ARN, description="Identity Center instance ARN, as sso-admin calls name it.")
    audit_role_arn: str = Field(
        default="", description="Role assumed in the audit account; empty uses the bot's own credentials."
    )
    org_role_arn: str = Field(
        default="", description="Role assumed in the organisation management account; empty uses the bot's own credentials."
    )
    logging_role_arn: str = Field(
        default="", description="Role assumed in the logging account; empty uses the bot's own credentials."
    )
    devops_agent_role_arn: str = Field(
        default="",
        description=(
            "Role assumed in the ops account to start and read AWS DevOps Agent investigations, its "
            "investigations table and its Agent Space lookups; empty leaves the investigation feature unconfigured."
        ),
    )


class AWSSettings(ConfigurationSlice):
    """Client tuning and the optional managed-organisation entry for AWS.

    Keys of [aws]:
        retry_max_attempts, retry_mode, connect_timeout_seconds, read_timeout_seconds,
        transient_retry_after_seconds, not_found_codes, unauthorized_codes, transient_codes.

    Environment only (the tenant entry; no tenant without an instance id):
        AWS__TENANT__INSTANCE_ID, AWS__TENANT__INSTANCE_ARN, AWS__TENANT__AUDIT_ROLE_ARN,
        AWS__TENANT__ORG_ROLE_ARN, AWS__TENANT__LOGGING_ROLE_ARN, AWS__TENANT__DEVOPS_AGENT_ROLE_ARN.
        An empty value counts as unset.
    """

    model_config = SettingsConfigDict(toml_table_header=("aws",), env_prefix="AWS__")

    tenant: AwsTenant | None = Field(default=None, description="The AWS organisation this instance manages.")

    retry_max_attempts: int = Field(
        default=3,
        description="Retries after the initial attempt (botocore max_attempts): 3 means four attempts in total.",
    )
    retry_mode: RetryMode = "standard"
    connect_timeout_seconds: int = 10
    read_timeout_seconds: int = 10
    transient_retry_after_seconds: int = Field(
        default=60, description="Retry hint attached to transient classifications, in seconds."
    )

    not_found_codes: list[str] = Field(
        default=[
            "ResourceNotFoundException",
            "NoSuchEntity",
            "NoSuchBucket",
            "NoSuchKey",
            "NotFoundException",
            "AccountNotFoundException",
            "TargetNotFoundException",
            "NoSuchConfigurationAggregatorException",
        ],
    )
    unauthorized_codes: list[str] = Field(
        default=[
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "InvalidClientTokenId",
            "SignatureDoesNotMatch",
            "ExpiredToken",
            "ExpiredTokenException",
            "TokenRefreshRequired",
            "InvalidAccessException",
        ],
    )
    transient_codes: list[str] = Field(
        default=[
            "Throttling",
            "ThrottlingException",
            "RequestLimitExceeded",
            "ProvisionedThroughputExceededException",
            "TooManyRequestsException",
            "RequestTimeout",
            "RequestTimeoutException",
            "ServiceUnavailable",
            "ServiceUnavailableException",
            "InternalFailure",
            "InternalServerError",
            "InternalServerErrorException",
            "InternalException",
            "ServiceException",
            "LimitExceededException",
        ],
    )

    @model_validator(mode="before")
    @classmethod
    def _tenant_and_its_values_go_together(cls, data: Any) -> Any:
        # Before validation: an empty value must count as unset, and the message must name the variable.
        if not isinstance(data, dict) or not isinstance(data.get("tenant"), dict):
            return data
        tenant = {key: value for key, value in data["tenant"].items() if not (key in _TENANT_FIELDS and value == "")}
        instance_id = _TENANT_VARIABLE.format("INSTANCE_ID")
        if "instance_id" not in tenant:
            for field in _TENANT_FIELDS[1:]:
                if field in tenant:
                    raise ValueError(f"{_TENANT_VARIABLE.format(field.upper())} is set but {instance_id} is not")
            # Anything else in the entry is left for validation to reject as an unknown key.
            return {**data, "tenant": tenant or None}
        return {**data, "tenant": tenant}

    @property
    def identity_store_id(self) -> str:
        """Identity store id of the managed organisation, or empty without a tenant."""
        return self.tenant.instance_id if self.tenant else ""

    @property
    def sso_instance_arn(self) -> str:
        """Identity Center instance ARN of the managed organisation, or empty without a tenant."""
        return self.tenant.instance_arn if self.tenant else ""

    @property
    def devops_agent_role_arn(self) -> str:
        """Role assumed in the ops account for AWS DevOps Agent investigations, or empty when unset.

        It is not in ``service_role_map``: the role also reaches DynamoDB and SSM in the ops
        account, so it is chosen by the investigation feature, never by service name.
        """
        return self.tenant.devops_agent_role_arn if self.tenant else ""

    @property
    def service_role_map(self) -> dict[str, str]:
        """Role ARN assumed for each service or account role name; a service without a role is absent."""
        if self.tenant is None:
            return {}
        roles = {
            "audit": self.tenant.audit_role_arn,
            "organizations": self.tenant.org_role_arn,
            "identitystore": self.tenant.org_role_arn,
            "sso-admin": self.tenant.org_role_arn,
            "logging": self.tenant.logging_role_arn,
            "ce": self.tenant.org_role_arn,
            "config": self.tenant.audit_role_arn,
            "guardduty": self.tenant.logging_role_arn,
            "securityhub": self.tenant.logging_role_arn,
        }
        return {service: arn for service, arn in roles.items() if arn}


@lru_cache(maxsize=1)
def get_aws_settings() -> AWSSettings:
    """Return the process-wide `AWSSettings` singleton."""
    return AWSSettings()
