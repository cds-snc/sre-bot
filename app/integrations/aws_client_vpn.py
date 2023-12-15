import boto3
import logging
import os

from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")


class AWSClientVPN:
    """
    Manage an account's client VPN endpoint.
    """

    STATUS_ON = "on"
    STATUS_OFF = "off"
    STATUS_TURNING_ON = "turning-on"
    STATUS_TURNING_OFF = "turning-off"
    STATUS_ERROR = "error"

    def __init__(self, client_vpn_id, assume_role_arn, region_name=AWS_REGION):
        """
        Initializes the AWSClientVPN class with the client VPN ID and an boto3 `ec2`
        client that has assumed the role required to manage the account's client VPN.
        """
        logging.info(
            f"Initializing AWSClientVPN for client_vpn_id: {client_vpn_id} with assume_role_arn: {assume_role_arn}"
        )
        self.client_vpn_id = client_vpn_id

        client = boto3.client("sts")
        response = client.assume_role(
            RoleArn=assume_role_arn, RoleSessionName="SREBot_Client_VPN_Role"
        )
        session = boto3.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )
        self.client = session.client("ec2", region_name=region_name)

    def get_status(self):
        """
        Returns the status of the client VPN endpoint.
        """
        status = "error"
        response = self.client.describe_client_vpn_endpoints(
            ClientVpnEndpointIds=[self.client_vpn_id]
        )

        if response["ClientVpnEndpoints"]:
            statusCode = response["ClientVpnEndpoints"][0]["Status"]["Code"]
            if statusCode == "available":
                status = self.STATUS_ON
            else:
                response = self.client.describe_client_vpn_target_networks(
                    ClientVpnEndpointId=self.client_vpn_id
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
        return status

    def turn_on(self):
        """
        Creates an association for the client VPN for all subnets that have an authorization rule.
        It identifies the subnets by the authorization rule's destination CIDR.  Any client VPN
        authorization rule for a single IP address `/32` is ignored.

        The result of this method is that the client VPN will begin associating subnets which
        can take up to 5 minutes before it completes.
        """
        status = self.get_status()
        if status in [self.STATUS_ON, self.STATUS_TURNING_ON]:
            logging.info(f"Client VPN is already on or turning on: {status}")
            return status

        status = self.STATUS_ERROR
        response = self.client.describe_client_vpn_authorization_rules(
            ClientVpnEndpointId=self.client_vpn_id
        )
        logging.info(
            f"Client VPN describe_client_vpn_authorization_rules response: {response}"
        )

        if response["AuthorizationRules"]:
            subnets_cidrs = [
                subnet["DestinationCidr"]
                for subnet in response["AuthorizationRules"]
                if not subnet["DestinationCidr"].endswith("/32")
            ]

            if subnets_cidrs:
                response = self.client.describe_subnets(
                    Filters=[{"Name": "cidr-block", "Values": subnets_cidrs}]
                )
                logging.info(f"Client VPN describe_subnets response: {response}")

                if response["Subnets"]:
                    subnet_ids = [subnet["SubnetId"] for subnet in response["Subnets"]]
                    for id in subnet_ids:
                        try:
                            response = self.client.associate_client_vpn_target_network(
                                ClientVpnEndpointId=self.client_vpn_id, SubnetId=id
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
                    status = self.STATUS_TURNING_ON

        logging.info(f"Client VPN turn_on status: {status}")
        return status

    def turn_off(self):
        status = self.get_status()
        if status in [self.STATUS_OFF, self.STATUS_TURNING_OFF]:
            logging.info(f"Client VPN is already off or turning off: {status}")
            return status

        status = self.STATUS_ERROR
        response = self.client.describe_client_vpn_target_networks(
            ClientVpnEndpointId=self.client_vpn_id
        )
        logging.info(
            f"Client VPN describe_client_vpn_target_networks response: {response}"
        )

        if response["ClientVpnTargetNetworks"]:
            association_ids = [
                association["AssociationId"]
                for association in response["ClientVpnTargetNetworks"]
                if association["Status"]["Code"] == "associated"
            ]

            if association_ids:
                for id in association_ids:
                    try:
                        response = self.client.disassociate_client_vpn_target_network(
                            ClientVpnEndpointId=self.client_vpn_id, AssociationId=id
                        )
                        logging.info(
                            f"Client VPN disassociate_client_vpn_target_network response: {response}"
                        )
                    except ClientError as error:
                        logging.error(
                            f"Client VPN disassociate_client_vpn_target_network error: {error}"
                        )
                        raise error
                status = self.STATUS_TURNING_OFF

        logging.info(f"Client VPN turn_off status: {status}")
        return status
