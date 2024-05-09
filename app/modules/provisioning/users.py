import logging


logger = logging.getLogger(__name__)

DISPLAY_KEYS = {"aws": "UserName", "google": "primaryEmail"}


def provision_entities(
    function,
    entities,
    execute=True,
    integration_name="unspecified",
    operation_name="processing",
    entity_name="entity(ies)",
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
    logger.info(
        f"{integration_name}:Starting {operation_name} of {len(entities)} {entity_name}"
    )
    for entity in entities:
        if execute:
            response = function(**entity, **kwargs)
            if response:
                logger.info(
                    f"{integration_name}:Successful {operation_name} of {entity_name} {entity[display_key] if display_key else entity}"
                )
                provisioned_entities.append({"entity": entity, "response": response})
            else:
                logger.error(
                    f"{integration_name}:Failed {operation_name} of {entity_name} {entity[display_key] if display_key else entity}"
                )
        else:
            logger.info(
                f"{integration_name}:DRY_RUN:Successful {operation_name} of {entity_name} {entity[display_key] if display_key else entity}"
            )
            provisioned_entities.append({"entity": entity, "response": None})
    logger.info(
        f"{integration_name}:Completed {operation_name} of {len(provisioned_entities)} {entity_name}"
    )
    return provisioned_entities
