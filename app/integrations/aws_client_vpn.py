import boto3
import datetime
import logging
import os

from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")


class AWSClientVPN:
    """
    Manage an account's client VPN endpoint.
    """

    DYNAMODB_TABLE = "sre_bot_data"
    STATUS_ON = "on"
    STATUS_OFF = "off"
    STATUS_TURNING_ON = "turning-on"
    STATUS_TURNING_OFF = "turning-off"
    STATUS_ERROR = "error"

    def __init__(
        self,
        name="",
        vpn_id="",
        assume_role_arn="",
        reason="",
        duration="",
        region_name=AWS_REGION,
    ):
        """
        Initializes the AWSClientVPN class with the client VPN ID and an boto3 `ec2`
        client that has assumed the role required to manage the account's client VPN.
        """
        self.name = name
        self.reason = reason
        self.duration = duration
        self.vpn_id = vpn_id
        self.assume_role_arn = assume_role_arn
        logging.info(f"Initializing AWSClientVPN: {vars(self)}")

        # Assume the product role to manage the client VPN
        if self.assume_role_arn:
            client = boto3.client("sts")
            response = client.assume_role(
                RoleArn=assume_role_arn, RoleSessionName="SREBot_Client_VPN_Role"
            )
            session = boto3.Session(
                aws_access_key_id=response["Credentials"]["AccessKeyId"],
                aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
                aws_session_token=response["Credentials"]["SessionToken"],
            )
            self.client_ec2 = session.client("ec2", region_name=region_name)

        # DynamoDB table is managed by the SRE Bot's role
        self.client_ddb = boto3.client("dynamodb", region_name=region_name)

    def get_status(self):
        """
        Returns the status of the client VPN endpoint.
        """
        status = "error"
        response = self.client_ec2.describe_client_vpn_endpoints(
            ClientVpnEndpointIds=[self.vpn_id]
        )

        if response.get("ClientVpnEndpoints"):
            statusCode = response["ClientVpnEndpoints"][0]["Status"]["Code"]
            if statusCode == "available":
                status = self.STATUS_ON
            else:
                response = self.client_ec2.describe_client_vpn_target_networks(
                    ClientVpnEndpointId=self.vpn_id
                )
                if response["ClientVpnTargetNetworks"]:
                    networkStatus = [
                        network["Status"].get("Code")
                        for network in response["ClientVpnTargetNetworks"]
                        if "Status" in network
                    ]
                    if "associating" in networkStatus:
                        status = self.STATUS_TURNING_ON
                    elif "disassociating" in networkStatus:
                        status = self.STATUS_TURNING_OFF
                else:
                    status = self.STATUS_OFF

        logging.info(f"Client VPN status: {status}")
        logging.info(f"Client VPN response: {response}")
        return {
            "status": status,
            "session": self.get_vpn_sesssion(),
        }

    def turn_on(self):
        """
        Creates an association for the client VPN for all subnets that have an authorization rule.
        It identifies the subnets by the authorization rule's destination CIDR.  Any client VPN
        authorization rule for a single IP address `/32` is ignored.

        The result of this method is that the client VPN will begin associating subnets which
        can take up to 5 minutes before it completes.
        """
        status = self.get_status()
        if status.get("status") in [self.STATUS_ON, self.STATUS_TURNING_ON]:
            logging.info(f"Client VPN is already on or turning on: {status}")
            self.put_vpn_session()
            return status.get("status")

        status = self.STATUS_ERROR
        response = self.client_ec2.describe_client_vpn_authorization_rules(
            ClientVpnEndpointId=self.vpn_id
        )
        logging.info(
            f"Client VPN describe_client_vpn_authorization_rules response: {response}"
        )

        if response.get("AuthorizationRules"):
            subnets_cidrs = [
                subnet["DestinationCidr"]
                for subnet in response["AuthorizationRules"]
                if not subnet["DestinationCidr"].endswith("/32")
            ]

            if subnets_cidrs:
                response = self.client_ec2.describe_subnets(
                    Filters=[{"Name": "cidr-block", "Values": subnets_cidrs}]
                )
                logging.info(f"Client VPN describe_subnets response: {response}")

                if response.get("Subnets"):
                    subnet_ids = [subnet["SubnetId"] for subnet in response["Subnets"]]
                    for id in subnet_ids:
                        try:
                            response = (
                                self.client_ec2.associate_client_vpn_target_network(
                                    ClientVpnEndpointId=self.vpn_id, SubnetId=id
                                )
                            )
                            logging.info(
                                f"Client VPN associate_client_vpn_target_network response: {response}"
                            )
                        except ClientError as error:
                            if (
                                error.response["Error"]["Code"]
                                == "InvalidClientVpnDuplicateAssociation"
                            ):
                                logging.info(
                                    f"Client VPN associate_client_vpn_target_network already associated: {error}"
                                )
                            else:
                                logging.error(
                                    f"Client VPN associate_client_vpn_target_network error: {error}"
                                )
                                raise error
                    self.put_vpn_session()
                    status = self.STATUS_TURNING_ON

        logging.info(f"Client VPN turn_on status: {status}")
        return status

    def turn_off(self):
        status = self.get_status()
        if status.get("status") in [self.STATUS_OFF, self.STATUS_TURNING_OFF]:
            logging.info(f"Client VPN is already off or turning off: {status}")
            return status.get("status")

        status = self.STATUS_ERROR
        response = self.client_ec2.describe_client_vpn_target_networks(
            ClientVpnEndpointId=self.vpn_id
        )
        logging.info(
            f"Client VPN describe_client_vpn_target_networks response: {response}"
        )

        if response.get("ClientVpnTargetNetworks"):
            association_ids = [
                association["AssociationId"]
                for association in response["ClientVpnTargetNetworks"]
                if association["Status"]["Code"] == "associated"
            ]

            if association_ids:
                for id in association_ids:
                    try:
                        response = (
                            self.client_ec2.disassociate_client_vpn_target_network(
                                ClientVpnEndpointId=self.vpn_id, AssociationId=id
                            )
                        )
                        logging.info(
                            f"Client VPN disassociate_client_vpn_target_network response: {response}"
                        )
                    except ClientError as error:
                        logging.error(
                            f"Client VPN disassociate_client_vpn_target_network error: {error}"
                        )
                        raise error
                self.delete_vpn_session()
                status = self.STATUS_TURNING_OFF

        logging.info(f"Client VPN turn_off status: {status}")
        return status

    def get_vpn_sesssion(self):
        """
        Returns the VPN session from the DynamoDB table.
        """
        if self.name:
            logging.info(f"Getting VPN session for {self.name}")
            response = self.client_ddb.get_item(
                TableName=self.DYNAMODB_TABLE,
                Key={
                    "PK": {"S": "vpn_session"},
                    "SK": {"S": self.name},
                },
            )
            logging.info(f"get_vpn_session response: {response}")
            if "Item" in response:
                return response["Item"]
        return None

    def get_vpn_sessions(self):
        """
        Returns all VPN sessions from the DynamoDB table.
        """
        logging.info("Getting all VPN sessions")
        response = self.client_ddb.query(
            TableName=self.DYNAMODB_TABLE,
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={
                ":pk": {"S": "vpn_session"},
            },
        )
        logging.info(f"get_vpn_sessions response: {response}")
        return response.get("Items")

    def put_vpn_session(self):
        """
        Adds the VPN session to the DynamoDB table.  If a session already exists, it will be updated.
        This allows a team to extend an existing session if required.
        """
        created_at = datetime.datetime.now()
        expires_at = created_at + datetime.timedelta(hours=float(self.duration))
        is_session = self.get_vpn_sesssion()
        logging.info(
            f"Putting VPN session for {self.name} with {self.reason} ({self.duration}) is_session: {is_session}"
        )

        # If the session doesn't exist, create it.  Otherwise, update it.
        if not is_session:
            response = self.client_ddb.put_item(
                TableName=self.DYNAMODB_TABLE,
                Item={
                    "PK": {"S": "vpn_session"},
                    "SK": {"S": self.name},
                    "reason": {"S": self.reason},
                    "duration": {"N": self.duration},
                    "vpn_id": {"S": self.vpn_id},
                    "assume_role_arn": {"S": self.assume_role_arn},
                    "created_at": {"N": str(created_at.timestamp())},
                    "expires_at": {"N": str(expires_at.timestamp())},
                },
            )
        else:
            response = self.client_ddb.update_item(
                TableName=self.DYNAMODB_TABLE,
                Key={
                    "PK": {"S": "vpn_session"},
                    "SK": {"S": self.name},
                },
                UpdateExpression="set reason = :reason, #dur = :duration, created_at = :created_at, expires_at = :expires_at, vpn_id = :vpn_id, assume_role_arn = :assume_role_arn",
                ExpressionAttributeValues={
                    ":reason": {"S": self.reason},
                    ":duration": {"N": self.duration},
                    ":created_at": {"N": str(created_at.timestamp())},
                    ":expires_at": {"N": str(expires_at.timestamp())},
                    ":vpn_id": {"S": self.vpn_id},
                    ":assume_role_arn": {"S": self.assume_role_arn},
                },
                ExpressionAttributeNames={"#dur": "duration"},
            )
        logging.info(f"put_vpn_session response: {response}")
        return response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def delete_vpn_session(self):
        """
        Deletes the VPN session from the DynamoDB table.
        """
        is_session = self.get_vpn_sesssion()
        logging.info(f"Deleting VPN session for {self.name} is_session: {is_session}")
        if is_session:
            response = self.client_ddb.delete_item(
                TableName=self.DYNAMODB_TABLE,
                Key={
                    "PK": {"S": "vpn_session"},
                    "SK": {"S": self.name},
                },
            )
            logging.info(f"delete_vpn_session response: {response}")
            return response["ResponseMetadata"]["HTTPStatusCode"] == 200
        else:
            return True
