from utils import filters
from integrations.sentinel import log_to_sentinel
from core.logging import get_module_logger


logger = get_module_logger()


def provision_entities(
    function,
    entities,
    execute=True,
    integration_name="Unspecified",
    operation_name="Processing",
    entity_name="Entity",
    display_key=None,
    **kwargs,
):
    """Provision entities in the specified integration's operation.

    Args:
        function (function): The function to execute for each entity.
        entities (list): The list of entities to provision.
        execute (bool, optional): Whether to execute the operation. Defaults to True.
        integration_name (str, optional): The name of the integration. Defaults to "unspecified".
        operation_name (str, optional): The name of the operation. Defaults to "processing".
        entity_name (str, optional): The name of the entity. Defaults to "entity(ies)".
        display_key (str, optional): The key to display in the logs. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the function.

    Returns:
        list: A list of created entities objects.
    """
    provisioned_entities = []
    if not entities:
        logger.info(
            "provision_entities_no_entities_to_process",
            integration=integration_name,
            entity=entity_name,
            operation=operation_name,
        )
        return provisioned_entities

    logger.info(
        "provision_entities_started",
        integration=integration_name,
        entity=entity_name,
        operation=operation_name,
        entities_count=len(entities),
    )

    for entity in entities:
        event = {
            "name": "provision_entities",
            "integration": integration_name,
            "entity": entity_name,
            "operation": operation_name,
            "status": "dry_run",
        }
        entity_string = (
            filters.get_nested_value(entity, display_key) if display_key else entity
        )
        if execute:
            response = function(**entity, **kwargs)
            if response:
                logger.info(
                    "provision_entity_successful",
                    integration=integration_name,
                    entity=entity_name,
                    operation=operation_name,
                    entity_value=entity_string,
                )
                event["status"] = "successful"
                log_to_sentinel(
                    event,
                    {"entity": entity},
                )
                provisioned_entities.append({"entity": entity, "response": response})
            else:
                event["status"] = "failed"
                logger.error(
                    "provision_entity_failed",
                    integration=integration_name,
                    entity=entity_name,
                    operation=operation_name,
                    entity_value=entity_string,
                )
                log_to_sentinel(
                    event,
                    {"entity": entity},
                )
        else:
            logger.info(
                "provision_entity_dry_run",
                integration=integration_name,
                entity=entity_name,
                operation=operation_name,
                entity_value=entity_string,
            )
            log_to_sentinel(
                event,
                {"entity": entity},
            )
            provisioned_entities.append({"entity": entity, "response": None})

    logger.info(
        "provision_entities_completed",
        integration=integration_name,
        entity=entity_name,
        operation=operation_name,
        provisioned_entities_count=len(provisioned_entities),
    )

    return provisioned_entities
