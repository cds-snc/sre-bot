"""AWS ElastiCache Management API wrapper.

Provides functions to interact with AWS ElastiCache API for cluster management
and monitoring using the client_next.py pattern.

Note: This module is for AWS API operations (describe, modify clusters).
For connecting to ElastiCache as a Redis client to store/retrieve data,
use integrations.aws.elasticache instead.

Functions:
- describe_replication_groups: Get information about replication groups
- describe_cache_clusters: Get information about cache clusters
- list_tags_for_resource: List tags for an ElastiCache resource
"""

from typing import Optional, List

from core.config import settings
from core.logging import get_module_logger
from integrations.aws.client_next import execute_aws_api_call
from infrastructure.operations.result import OperationResult

logger = get_module_logger()

AWS_REGION = settings.aws.AWS_REGION


def describe_replication_groups(
    replication_group_id: Optional[str] = None,
    **kwargs,
) -> OperationResult:
    """
    Describe ElastiCache replication groups.

    Args:
        replication_group_id (str, optional): Specific replication group ID
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response with replication group info
    """
    params = {}
    if replication_group_id:
        params["ReplicationGroupId"] = replication_group_id

    return execute_aws_api_call(
        service_name="elasticache",
        method="describe_replication_groups",
        keys=["ReplicationGroups"],
        force_paginate=True,
        **params,
        **kwargs,
    )


def describe_cache_clusters(
    cache_cluster_id: Optional[str] = None,
    **kwargs,
) -> OperationResult:
    """
    Describe ElastiCache cache clusters.

    Args:
        cache_cluster_id (str, optional): Specific cache cluster ID
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response with cache cluster info
    """
    params = {}
    if cache_cluster_id:
        params["CacheClusterId"] = cache_cluster_id

    return execute_aws_api_call(
        service_name="elasticache",
        method="describe_cache_clusters",
        keys=["CacheClusters"],
        force_paginate=True,
        **params,
        **kwargs,
    )


def list_tags_for_resource(
    resource_name: str,
    **kwargs,
) -> OperationResult:
    """
    List tags for an ElastiCache resource.

    Args:
        resource_name (str): ARN of the ElastiCache resource
        **kwargs: Additional parameters for the API call

    Returns:
        OperationResult: Standardized response with tags
    """
    return execute_aws_api_call(
        service_name="elasticache",
        method="list_tags_for_resource",
        ResourceName=resource_name,
        **kwargs,
    )


def get_cluster_endpoint(replication_group_id: str) -> OperationResult:
    """
    Get the primary endpoint for an ElastiCache replication group.

    Args:
        replication_group_id (str): The replication group ID

    Returns:
        OperationResult: Success with endpoint data or error
    """
    result = describe_replication_groups(replication_group_id=replication_group_id)

    if not result.is_success:
        return result

    if not result.data or len(result.data) == 0:
        return OperationResult.permanent_error(
            message=f"Replication group not found: {replication_group_id}",
            error_code="NOT_FOUND",
        )

    replication_group = result.data[0]

    # Extract endpoint information
    endpoint_data = {
        "replication_group_id": replication_group_id,
        "status": replication_group.get("Status"),
    }

    # Get primary endpoint
    if "NodeGroups" in replication_group and len(replication_group["NodeGroups"]) > 0:
        node_group = replication_group["NodeGroups"][0]
        if "PrimaryEndpoint" in node_group:
            endpoint_data["primary_endpoint"] = {
                "address": node_group["PrimaryEndpoint"].get("Address"),
                "port": node_group["PrimaryEndpoint"].get("Port"),
            }
        if "ReaderEndpoint" in node_group:
            endpoint_data["reader_endpoint"] = {
                "address": node_group["ReaderEndpoint"].get("Address"),
                "port": node_group["ReaderEndpoint"].get("Port"),
            }

    logger.info(
        "elasticache_endpoint_retrieved",
        replication_group_id=replication_group_id,
        status=endpoint_data.get("status"),
    )

    return OperationResult.success(
        message=f"Retrieved endpoint for {replication_group_id}",
        data=endpoint_data,
    )


def healthcheck() -> bool:
    """
    Check if ElastiCache API is accessible.

    Returns:
        bool: True if API is accessible, False otherwise
    """
    try:
        result = describe_replication_groups()
        return result.is_success
    except Exception as e:
        logger.error(
            "elasticache_api_healthcheck_failed",
            error=str(e),
        )
        return False
