import boto3
import logging
import os

from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")

class AWSClientVPN:
    def __init__(self, client_vpn_id, region_name=AWS_REGION):
        self.client = boto3.client('ec2', region_name=region_name)
        self.client_vpn_id = client_vpn_id

    def get_status(self):
        status = "error"
        response = self.client.describe_client_vpn_endpoints(ClientVpnEndpointIds=[self.client_vpn_id])
        
        if response['ClientVpnEndpoints']:
            statusCode = response['ClientVpnEndpoints'][0]['Status']['Code']
            if statusCode == "available":
                status = "on"
            else:
                response = self.client.describe_client_vpn_target_networks(ClientVpnEndpointId=self.client_vpn_id)
                if response["ClientVpnTargetNetworks"]:
                    networkStatus = [network["Status"].get("Code") for network in response["ClientVpnTargetNetworks"] if "Status" in network]
                    if "associating" in networkStatus:
                        status = "turning-on"
                    elif "disassociating" in networkStatus:
                        status = "turning-off"
                    else:
                        status = "off"
        else:
            logging.
        return status


    def turn_on(self):
        status = self.get_status()
        if status in ["on", "turning-on"]:
            print("VPN is already on")
            return

        response = self.client.describe_client_vpn_authorization_rules(ClientVpnEndpointId=self.client_vpn_id)
        if response['AuthorizationRules']:
            subnets_cidrs = [subnet['DestinationCidr'] for subnet in response['AuthorizationRules'] if not subnet['DestinationCidr'].endswith('/32')]
            
            if subnets_cidrs:
                response = self.client.describe_subnets(
                    Filters=[
                        {'Name': 'cidr-block', 'Values': subnets_cidrs}
                    ]
                )
                if response["Subnets"]:
                    subnet_ids = [subnet['SubnetId'] for subnet in response["Subnets"]]
                    for id in subnet_ids:
                        try:
                            response = self.client.associate_client_vpn_target_network(
                                ClientVpnEndpointId=self.client_vpn_id,
                                SubnetId=id
                            )
                        except ClientError as error:
                            if error.response['Error']['Code'] != 'InvalidClientVpnDuplicateAssociation':
                               raise error
    

    def turn_off(self):
        response = self.client.describe_client_vpn_target_networks(ClientVpnEndpointId=self.client_vpn_id)
        if response["ClientVpnTargetNetworks"]:
            association_ids = [association['AssociationId'] for association in response["ClientVpnTargetNetworks"] if association['Status']['Code'] == 'associated']

            if association_ids:
                for id in association_ids:
                    try:
                        response = self.client.disassociate_client_vpn_target_network(
                            ClientVpnEndpointId=self.client_vpn_id,
                            AssociationId=id
                        )
                        print(response)
                    except ClientError as error:
                        print(error)


vpn = AWSClientVPN("cvpn-endpoint-010b27fdb479d5e19")
print(vpn.turn_off())