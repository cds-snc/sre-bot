import datetime
import logging

from integrations.aws_client_vpn import AWSClientVPN

logging.basicConfig(level=logging.INFO)


def client_vpn_turn_off():
    """
    Turn off expired client VPN sessions.
    """
    logging.info("Looking for expired client VPN sessions")

    client_vpn = AWSClientVPN()
    vpn_sessions = client_vpn.get_vpn_sessions()
    for session in vpn_sessions:
        logging.info("Found VPN session %s", session)
        remaining_seconds = (
            float(session["expires_at"]["N"]) - datetime.datetime.now().timestamp()
        )
        if remaining_seconds < 0:
            logging.info("Session %s has expired, turning off", session["SK"]["S"])
            AWSClientVPN(
                name=session["SK"]["S"],
                vpn_id=session["vpn_id"]["S"],
                assume_role_arn=session["assume_role_arn"]["S"],
            ).turn_off()
