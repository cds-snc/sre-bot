import logging
from utils import filters
from integrations.sentinel import log_to_sentinel


logger = logging.getLogger(__name__)


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
            f"{integration_name}:{entity_name}:{operation_name}: No entities to process"
        )
        return provisioned_entities
    logger.info(
        f"{integration_name}:{entity_name}:{operation_name}: Started processing {len(entities)} entities"
    )
    for entity in entities:
        entity_string = (
            filters.get_nested_value(entity, display_key) if display_key else entity
        )
        if execute:
            response = function(**entity, **kwargs)
            if response:
                logger.info(
                    f"{integration_name}:{entity_name}:{operation_name}:Successful: {entity_string}"
                )
                log_to_sentinel(
                    f"{integration_name}_{entity_name}_{operation_name}_successful",
                    {"entity": entity},
                )
                provisioned_entities.append({"entity": entity, "response": response})
            else:
                logger.error(
                    f"{integration_name}:{entity_name}:{operation_name}:Failed: {entity_string}"
                )
                log_to_sentinel(
                    f"{integration_name}_{entity_name}_{operation_name}_failed",
                    {"entity": entity},
                )
        else:
            logger.info(
                f"{integration_name}:{entity_name}:{operation_name}:Successful:DRY_RUN: {entity_string}"
            )
            log_to_sentinel(
                f"{integration_name}_{entity_name}_{operation_name}_dry_run",
                {"entity": entity},
            )
            provisioned_entities.append({"entity": entity, "response": None})
    logger.info(
        f"{integration_name}:{entity_name}:{operation_name}: Completed processing {len(provisioned_entities)} entities"
    )
    return provisioned_entities
