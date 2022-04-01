from integrations import google_drive

help_text = """
\n `/sre incident create-folder <folder_name>` - create a folder for a team in the incident drive
\n `/sre incident help` - show this help text
\n `/sre incident list-folders` - list all folders in the incident drive"""


def handle_incident_command(args, client, body, respond):

    if len(args) == 0:
        respond(help_text)
        return

    action, *args = args
    match action:
        case "create-folder":
            name = " ".join(args)
            respond(google_drive.create_folder(name))
        case "help":
            respond(help_text)
        case "list-folders":
            names = list(n["name"] for n in google_drive.list_folders())
            respond(", ".join(names))
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )
