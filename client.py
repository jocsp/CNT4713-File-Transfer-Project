"""File-transfer client with TCP connection helpers, state, and cleanup."""

import socket


class FileTransferClient:
    def __init__(self):
        # Connection details and sockets are populated by the connect methods.
        self.server_address = None
        self.control_port = None
        self.data_port = None
        self.control_socket = None
        self.data_socket = None

        # A username is recorded only after a successful login.
        self.username = None
        self.running = False

    def run(self):
        # Print the startup message and process interactive commands until quit.
        pass

    def read_command(self):
        # Read and parse user input without hardcoding addresses, names, or ports.
        pass

    def dispatch_command(self, command, arguments):
        # Validate command arguments and connection state, then select a handler.
        pass

    def connect(self, server_address, control_port):
        if self.control_socket is not None:
            raise RuntimeError("Close the existing connection before reconnecting.")

        control_port = int(control_port)
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            connection.connect((server_address, control_port))
        except (OSError, ValueError, TypeError, OverflowError):
            connection.close()
            raise

        self.control_socket = connection
        self.server_address = server_address
        self.control_port = control_port
        # TODO: Read the Chat handshake and advertised port once its format is known,
        # then call connect_data_socket(). TCP connection alone is not login.

    def connect_data_socket(self, server_address, data_port):
        if self.control_socket is None:
            raise RuntimeError("Open a control connection before the data connection.")
        if self.data_socket is not None:
            raise RuntimeError("The data connection is already open.")

        data_port = int(data_port)
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            connection.connect((server_address, data_port))
        except (OSError, ValueError, TypeError, OverflowError):
            connection.close()
            raise

        self.data_socket = connection
        self.data_port = data_port
        # The handshake caller must print the required status after validating it.

    def login(self, username):
        # Send the Chat login request and display the required status message.
        pass

    def handle_chat_command(self, command, arguments):
        # Preserve earlier Chat commands once their missing specification is available.
        pass

    def list_files(self):
        # Send `list`, receive the data-channel listing, and print the required result.
        pass

    def store_file(self, filename):
        # Send `stor <filename>`, upload the local file, and display the result.
        pass

    def retrieve_file(self, filename):
        # Send `retr <filename>`, save received bytes locally, and display the result.
        pass

    def delete_file(self, filename):
        # Send `dele <filename>` and display the returned deletion status.
        pass

    def quit(self):
        # Send `quit`, display its status, and close the client's connections.
        pass

    def send_command(self, command, argument=None):
        """Send one UTF-8 command line; LF framing awaits Chat-spec confirmation."""
        if self.control_socket is None:
            raise RuntimeError("Open a control connection before sending commands.")
        if not isinstance(command, str) or not command or any(
            character.isspace() for character in command
        ):
            raise ValueError("The command must be a single nonempty word.")
        if argument is not None and (
            not isinstance(argument, str) or "\r" in argument or "\n" in argument
        ):
            raise ValueError("The argument must be text without line breaks.")

        message = command if argument is None else f"{command} {argument}"
        self.control_socket.sendall((message + "\n").encode("utf-8"))

    def receive_response(self, connection, data_length=0):
        """Return (status, bytes), reading exactly data_length bytes after the header.

        Payload size must be known by the caller; no length field is added to the
        wire protocol. The default reads only the status and blank separator.
        """
        if connection is None:
            raise RuntimeError("A response requires an open connection.")
        if type(data_length) is not int or data_length < 0:
            raise ValueError("The response data length must be a nonnegative integer.")

        lines = []
        for _ in range(2):
            line = bytearray()
            while True:
                # Read only the header so file bytes or the next reply stay unread.
                byte = connection.recv(1)
                if not byte:
                    raise EOFError("Connection closed before the response header completed.")
                if byte == b"\n":
                    break
                line.extend(byte)
                if len(line) > 16:
                    raise ValueError("Response header line is too long.")
            lines.append(bytes(line).removesuffix(b"\r"))

        if lines[0] not in (b"200", b"500") or lines[1] != b"":
            raise ValueError("Expected status 200 or 500 followed by a blank line.")

        status_code = int(lines[0])
        data = bytearray()
        # Failure responses have no data, even when a successful reply would.
        if status_code == 200:
            while len(data) < data_length:
                chunk = connection.recv(min(65536, data_length - len(data)))
                if not chunk:
                    raise EOFError("Connection closed before the response data completed.")
                data.extend(chunk)
        return status_code, bytes(data)

    def send_file(self, data_socket, source):
        # Send all file bytes using the required transfer-completion framing.
        pass

    def receive_file(self, data_socket, destination):
        # Receive all file bytes using the required transfer-completion framing.
        pass

    def close_connections(self):
        for attribute in ("data_socket", "control_socket"):
            connection = getattr(self, attribute)
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    # Still release the other socket if this close fails.
                    pass
                finally:
                    setattr(self, attribute, None)

        self.server_address = None
        self.control_port = None
        self.data_port = None
        self.username = None
        # Keep the input loop running so the user can reconnect; quit will stop it.


def main():
    # Start the interactive client for `python client.py` with the required output.
    pass
