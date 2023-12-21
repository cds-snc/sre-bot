from unittest.mock import call, MagicMock, patch

from integrations.aws_client_vpn import AWSClientVPN

mock_boto3 = MagicMock()
AWS_REGION = "test-region"


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_init_with_assume_role_arn():
    assume_role_response = {
        "Credentials": {
            "AccessKeyId": "test-access-key-id",
            "SecretAccessKey": "test-secret-access-key",
            "SessionToken": "test-session-token",
        }
    }
    sts_client = mock_boto3.client.return_value
    sts_client.assume_role.return_value = assume_role_response

    vpn = AWSClientVPN(
        name="TestVPN",
        vpn_id="vpn-123",
        assume_role_arn="arn:aws:iam::123456789012:role/TestRole",
    )
    assert vpn.name == "TestVPN"
    assert vpn.vpn_id == "vpn-123"
    assert vpn.assume_role_arn == "arn:aws:iam::123456789012:role/TestRole"
    assert hasattr(vpn, "client_ec2")
    sts_client.assume_role.assert_called_once_with(
        RoleArn="arn:aws:iam::123456789012:role/TestRole",
        RoleSessionName="SREBot_Client_VPN_Role",
    )
    mock_boto3.Session.assert_called_once_with(
        aws_access_key_id="test-access-key-id",
        aws_secret_access_key="test-secret-access-key",
        aws_session_token="test-session-token",
    )


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_init_without_assume_role_arn():
    vpn = AWSClientVPN(name="TestVPN", vpn_id="vpn-123")
    assert vpn.name == "TestVPN"
    assert vpn.vpn_id == "vpn-123"
    assert vpn.assume_role_arn == ""
    assert not hasattr(vpn, "client_ec2")


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_status_available():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    mock_client_ec2.describe_client_vpn_endpoints.return_value = {
        "ClientVpnEndpoints": [{"Status": {"Code": "available"}}]
    }
    vpn.get_vpn_sesssion = MagicMock(return_value={"session_info": "mocked_session"})

    status = vpn.get_status()

    mock_client_ec2.describe_client_vpn_endpoints.assert_called_once_with(
        ClientVpnEndpointIds=["vpn-123"]
    )
    assert status["status"] == vpn.STATUS_ON
    assert status["session"] == {"session_info": "mocked_session"}


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_status_associating():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    mock_client_ec2.describe_client_vpn_endpoints.return_value = {
        "ClientVpnEndpoints": [{"Status": {"Code": "pending-association"}}]
    }
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {
        "ClientVpnTargetNetworks": [{"Status": {"Code": "associating"}}]
    }
    vpn.get_vpn_sesssion = MagicMock(return_value={"session_info": "mocked_session"})

    status = vpn.get_status()

    mock_client_ec2.describe_client_vpn_target_networks.assert_called_once_with(
        ClientVpnEndpointId="vpn-123"
    )
    assert status["status"] == vpn.STATUS_TURNING_ON
    assert status["session"] == {"session_info": "mocked_session"}


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_status_no_endpoints():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    mock_client_ec2.describe_client_vpn_endpoints.return_value = {}
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {}
    vpn.get_vpn_sesssion = MagicMock(return_value=None)

    status = vpn.get_status()

    assert status["status"] == vpn.STATUS_ERROR
    assert status["session"] is None


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_status_disassociating():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    mock_client_ec2.describe_client_vpn_endpoints.return_value = {
        "ClientVpnEndpoints": [{"Status": {"Code": "pending-disassociation"}}]
    }
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {
        "ClientVpnTargetNetworks": [{"Status": {"Code": "disassociating"}}]
    }
    vpn.get_vpn_sesssion = MagicMock(return_value={"session_info": "mocked_session"})

    status = vpn.get_status()

    assert status["status"] == vpn.STATUS_TURNING_OFF
    assert status["session"] == {"session_info": "mocked_session"}


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_on_already_on():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_ON})
    vpn.put_vpn_session = MagicMock()

    status = vpn.turn_on()

    assert status == vpn.STATUS_ON
    vpn.put_vpn_session.assert_called_once()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_on_turning_on():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_TURNING_ON})
    vpn.put_vpn_session = MagicMock()

    status = vpn.turn_on()

    assert status == vpn.STATUS_TURNING_ON
    vpn.put_vpn_session.assert_called_once()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_on_no_authorization_rules():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_ERROR})
    mock_client_ec2.describe_client_vpn_authorization_rules.return_value = {}

    vpn.put_vpn_session = MagicMock()

    status = vpn.turn_on()

    assert status == vpn.STATUS_ERROR
    assert not vpn.put_vpn_session.called
    assert not mock_client_ec2.describe_subnets.called
    assert (
        not mock_client_ec2.associate_client_vpn_target_networkdescribe_subnets.called
    )


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_on_associating_subnets():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_OFF})
    mock_client_ec2.describe_client_vpn_authorization_rules.return_value = {
        "AuthorizationRules": [
            {"DestinationCidr": "10.0.1.0/24"},
            {"DestinationCidr": "10.0.2.0/24"},
            {"DestinationCidr": "10.0.0.2/32"},
        ]
    }
    mock_client_ec2.describe_subnets.return_value = {
        "Subnets": [{"SubnetId": "subnet-123"}, {"SubnetId": "subnet-456"}]
    }
    mock_client_ec2.associate_client_vpn_target_network.return_value = {}

    vpn.put_vpn_session = MagicMock()

    status = vpn.turn_on()

    assert status == vpn.STATUS_TURNING_ON
    mock_client_ec2.describe_client_vpn_authorization_rules.assert_called_once_with(
        ClientVpnEndpointId="vpn-123"
    )
    mock_client_ec2.describe_subnets.assert_called_once_with(
        Filters=[{"Name": "cidr-block", "Values": ["10.0.1.0/24", "10.0.2.0/24"]}]
    )
    mock_client_ec2.associate_client_vpn_target_network.assert_has_calls(
        [
            call(
                ClientVpnEndpointId="vpn-123",
                SubnetId="subnet-123",
            ),
            call(
                ClientVpnEndpointId="vpn-123",
                SubnetId="subnet-456",
            ),
        ]
    )

    vpn.put_vpn_session.assert_called_once()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_on_associating_error():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_OFF})
    mock_client_ec2.describe_client_vpn_authorization_rules.return_value = {
        "AuthorizationRules": [{"DestinationCidr": "10.0.0.0/16"}]
    }
    mock_client_ec2.describe_subnets.return_value = {
        "Subnets": [{"SubnetId": "subnet-123"}]
    }
    error_response = {"Error": {"Code": "InvalidClientVpnDuplicateAssociation"}}
    mock_client_ec2.associate_client_vpn_target_network.side_effect = Exception(
        error_response
    )

    vpn.put_vpn_session = MagicMock()

    try:
        vpn.turn_on()
    except Exception as e:
        assert str(e) == str(error_response)
    assert not vpn.put_vpn_session.called


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_off_already_off():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_OFF})

    status = vpn.turn_off()

    assert status == vpn.STATUS_OFF
    mock_client_ec2.describe_client_vpn_target_networks.assert_not_called()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_off_turning_off():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_TURNING_OFF})

    status = vpn.turn_off()

    assert status == vpn.STATUS_TURNING_OFF
    mock_client_ec2.describe_client_vpn_target_networks.assert_not_called()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_off_no_associated_networks():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_ERROR})
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {}

    vpn.delete_vpn_session = MagicMock()

    status = vpn.turn_off()

    assert status == vpn.STATUS_ERROR
    assert not vpn.delete_vpn_session.called
    mock_client_ec2.describe_client_vpn_target_networks.assert_called_once_with(
        ClientVpnEndpointId="vpn-123"
    )


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_off_associating_networks():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_ON})
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {
        "ClientVpnTargetNetworks": [
            {"AssociationId": "assoc-123", "Status": {"Code": "associated"}},
            {"AssociationId": "assoc-456", "Status": {"Code": "associated"}},
            {"AssociationId": "assoc-789", "Status": {"Code": "pending-association"}},
        ]
    }
    mock_client_ec2.disassociate_client_vpn_target_network.return_value = {}

    vpn.delete_vpn_session = MagicMock()

    status = vpn.turn_off()

    assert status == vpn.STATUS_TURNING_OFF
    mock_client_ec2.describe_client_vpn_target_networks.assert_called_once_with(
        ClientVpnEndpointId="vpn-123"
    )
    mock_client_ec2.disassociate_client_vpn_target_network.assert_has_calls(
        [
            call(
                ClientVpnEndpointId="vpn-123",
                AssociationId="assoc-123",
            ),
            call(
                ClientVpnEndpointId="vpn-123",
                AssociationId="assoc-456",
            ),
        ]
    )
    vpn.delete_vpn_session.assert_called_once()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_turn_off_disassociation_error():
    mock_client_ec2 = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client_ec2

    vpn = AWSClientVPN(
        vpn_id="vpn-123", assume_role_arn="arn:aws:iam::123456789012:role/TestRole"
    )
    vpn.get_status = MagicMock(return_value={"status": vpn.STATUS_ON})
    mock_client_ec2.describe_client_vpn_target_networks.return_value = {
        "ClientVpnTargetNetworks": [
            {"AssociationId": "assoc-123", "Status": {"Code": "associated"}}
        ]
    }
    error_response = {"Error": {"Code": "DisassociateError"}}
    mock_client_ec2.disassociate_client_vpn_target_network.side_effect = Exception(
        error_response
    )

    vpn.delete_vpn_session = MagicMock()

    try:
        vpn.turn_off()
    except Exception as e:
        assert str(e) == str(error_response)
    assert not vpn.delete_vpn_session.called


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_vpn_session_with_name():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    vpn = AWSClientVPN(name="test", vpn_id="vpn-123")
    mock_client_ddb.get_item.return_value = {"Item": {"session_info": "mocked_session"}}

    session = vpn.get_vpn_sesssion()

    assert session == {"session_info": "mocked_session"}
    mock_client_ddb.get_item.assert_called_once_with(
        TableName=vpn.DYNAMODB_TABLE,
        Key={
            "PK": {"S": "vpn_session"},
            "SK": {"S": "test"},
        },
    )


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_vpn_session_without_name():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    vpn = AWSClientVPN(name="", vpn_id="vpn-123")
    mock_client_ddb.get_item.return_value = {}

    session = vpn.get_vpn_sesssion()

    assert session is None
    mock_client_ddb.get_item.assert_not_called()


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_vpn_sessions():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    mock_items = [{"session_info": "session1"}, {"session_info": "session2"}]
    mock_client_ddb.query.return_value = {"Items": mock_items}

    vpn = AWSClientVPN()
    sessions = vpn.get_vpn_sessions()

    assert sessions == mock_items
    mock_client_ddb.query.assert_called_once_with(
        TableName=vpn.DYNAMODB_TABLE,
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": {"S": "vpn_session"}},
    )


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_get_vpn_sessions_no_items():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    mock_client_ddb.query.return_value = {}

    vpn = AWSClientVPN()
    sessions = vpn.get_vpn_sessions()

    assert sessions is None


@patch("integrations.aws_client_vpn.datetime")
@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_put_vpn_session_create_session(mock_datetime):
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb
    mock_datetime.datetime.now.return_value.timestamp.return_value = 1640082800
    mock_datetime.datetime.now.return_value.__add__.return_value.timestamp.return_value = (
        1640086400
    )

    vpn = AWSClientVPN(
        name="test",
        vpn_id="vpn-123",
        reason="foobar",
        duration="1",
        assume_role_arn="arn:test",
    )
    vpn.get_vpn_sesssion = MagicMock(return_value=None)

    mock_client_ddb.put_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }

    response = vpn.put_vpn_session()

    mock_client_ddb.put_item.assert_called_once_with(
        TableName=vpn.DYNAMODB_TABLE,
        Item={
            "PK": {"S": "vpn_session"},
            "SK": {"S": "test"},
            "reason": {"S": "foobar"},
            "duration": {"N": "1"},
            "vpn_id": {"S": "vpn-123"},
            "assume_role_arn": {"S": "arn:test"},
            "created_at": {"N": "1640082800"},
            "expires_at": {"N": "1640086400"},
        },
    )
    mock_datetime.timedelta.assert_called_once_with(hours=float(vpn.duration))

    assert response


@patch("integrations.aws_client_vpn.datetime")
@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_put_vpn_session_update_session(mock_datetime):
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb
    mock_datetime.datetime.now.return_value.timestamp.return_value = 1640082800
    mock_datetime.datetime.now.return_value.__add__.return_value.timestamp.return_value = (
        1640097200
    )

    vpn = AWSClientVPN(
        name="test",
        vpn_id="vpn-123",
        reason="foobar",
        duration="4",
        assume_role_arn="arn:test",
    )
    vpn.get_vpn_sesssion = MagicMock(return_value={"existing_session": "data"})

    mock_client_ddb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }

    response = vpn.put_vpn_session()

    mock_client_ddb.update_item.assert_called_once_with(
        TableName=vpn.DYNAMODB_TABLE,
        Key={
            "PK": {"S": "vpn_session"},
            "SK": {"S": "test"},
        },
        UpdateExpression="set reason = :reason, #dur = :duration, created_at = :created_at, expires_at = :expires_at, vpn_id = :vpn_id, assume_role_arn = :assume_role_arn",
        ExpressionAttributeValues={
            ":reason": {"S": "foobar"},
            ":duration": {"N": "4"},
            ":created_at": {"N": "1640082800"},
            ":expires_at": {"N": "1640097200"},
            ":vpn_id": {"S": "vpn-123"},
            ":assume_role_arn": {"S": "arn:test"},
        },
        ExpressionAttributeNames={"#dur": "duration"},
    )
    mock_datetime.timedelta.assert_called_once_with(hours=float(vpn.duration))

    assert response


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_delete_vpn_session_with_session():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    vpn = AWSClientVPN(name="test", vpn_id="vpn-123", assume_role_arn="arn:test")
    vpn.get_vpn_sesssion = MagicMock(return_value={"session_key": "session_value"})

    mock_client_ddb.delete_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }

    response = vpn.delete_vpn_session()

    mock_client_ddb.delete_item.assert_called_once_with(
        TableName=vpn.DYNAMODB_TABLE,
        Key={"PK": {"S": "vpn_session"}, "SK": {"S": "test"}},
    )
    assert response


@patch("integrations.aws_client_vpn.boto3", mock_boto3)
@patch("integrations.aws_client_vpn.AWS_REGION", AWS_REGION)
def test_delete_vpn_session_without_session():
    mock_client_ddb = MagicMock()
    mock_boto3.client.return_value = mock_client_ddb

    vpn = AWSClientVPN(name="test", vpn_id="vpn-123", assume_role_arn="arn:test")
    vpn.get_vpn_sesssion = MagicMock(return_value=None)

    response = vpn.delete_vpn_session()
    mock_client_ddb.delete_item.assert_not_called()
    assert response
