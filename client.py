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
        print("Starting client…")
        self.running = True
        try:
            while self.running:
                try:
                    command, arguments = self.read_command()
                except (EOFError, KeyboardInterrupt):
                    break
                if not command:
                    continue
                try:
                    self.dispatch_command(command, arguments)
                except (OSError, EOFError) as error:
                    print(f"Connection error: {error}")
                    self.close_connections()
                except (ValueError, RuntimeError, NotImplementedError) as error:
                    print(f"Error: {error}")
        finally:
            self.close_connections()
            self.running = False

    def read_command(self):
        parts = input().strip().split(None, 1)
        if not parts:
            return "", ""
        return parts[0].lower(), parts[1] if len(parts) == 2 else ""

    def dispatch_command(self, command, arguments):
        if command == "connect":
            parts = arguments.split()
            if len(parts) != 2:
                raise ValueError("Usage: connect <address> <port>")
            return self.connect(parts[0], parts[1])
        if command == "login":
            return self.login(arguments)
        if command == "quit":
            if arguments:
                raise ValueError("Usage: quit")
            return self.quit()
        if command == "list":
            if arguments:
                raise ValueError("Usage: list")
            return self.list_files()
        if command in ("stor", "retr", "dele", "who", "broadcast", "private"):
            raise NotImplementedError(f"The {command} command is not implemented yet.")
        raise ValueError(f"Unknown command: {command}")

    def connect(self, server_address, control_port):
        if self.control_socket is not None:
            raise RuntimeError("Close the existing connection before reconnecting.")

        control_port = int(control_port)
        if not 1 <= control_port <= 65535:
            raise ValueError("The control port must be between 1 and 65535.")
        if not isinstance(server_address, str) or not server_address or any(
            character.isspace() for character in server_address
        ):
            raise ValueError("The server address must be a single nonempty value.")

        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket = connection
        try:
            connection.settimeout(10)
            connection.connect((server_address, control_port))
            self.server_address = server_address
            self.control_port = control_port
            self.send_command("connect", f"{server_address} {control_port}")

            status_code, _ = self.receive_response(connection)
            if status_code != 200:
                raise ConnectionError("500 status code received. Connection rejected.")

            port_text = self.receive_text_line(connection, max_length=5)
            if not port_text.isascii() or not port_text.isdecimal():
                raise ValueError("The server returned an invalid data port.")
            data_port = int(port_text)
            if not 1 <= data_port <= 65535:
                raise ValueError("The data port must be between 1 and 65535.")

            print(
                "200 status code received. Starting data connection on port "
                f"{data_port}"
            )
            self.connect_data_socket(server_address, data_port)
            connection.settimeout(None)
        except (OSError, EOFError, ValueError, TypeError):
            self.close_connections()
            raise

    def connect_data_socket(self, server_address, data_port):
        if self.control_socket is None:
            raise RuntimeError("Open a control connection before the data connection.")
        if self.data_socket is not None:
            raise RuntimeError("The data connection is already open.")

        data_port = int(data_port)
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            connection.settimeout(10)
            connection.connect((server_address, data_port))
            connection.settimeout(None)
        except (OSError, ValueError, TypeError, OverflowError):
            connection.close()
            raise

        self.data_socket = connection
        self.data_port = data_port

    def receive_text_line(self, connection, max_length=65536):
        """Read one UTF-8 LF/CRLF line without consuming the following message."""
        if connection is None:
            raise RuntimeError("Reading text requires an open connection.")
        if type(max_length) is not int or max_length < 0:
            raise ValueError("The line limit must be a nonnegative integer.")

        line = bytearray()
        while True:
            byte = connection.recv(1)
            if not byte:
                raise EOFError("Connection closed before the text line completed.")
            if byte == b"\n":
                payload = bytes(line).removesuffix(b"\r")
                if len(payload) > max_length:
                    raise ValueError("Response text line is too long.")
                return payload.decode("utf-8")
            line.extend(byte)
            # Allow one extra byte only for a possible CRLF terminator.
            if len(line) > max_length and not (
                len(line) == max_length + 1 and byte == b"\r"
            ):
                raise ValueError("Response text line is too long.")

    def login(self, username):
        self._require_connection()
        if not username or any(character.isspace() for character in username):
            raise ValueError("Username must be a single nonempty word.")
        if self.username is not None:
            raise ValueError("Already logged in.")
        self.send_command("login", username)
        status, _ = self.receive_response(self.data_socket)
        if status == 200:
            self.username = username
            print("200 status code received. Login successful")
        else:
            print("500 status code received. Login failed")
        return status

    def _require_connection(self, logged_in=False):
        if self.control_socket is None or self.data_socket is None:
            raise ValueError("Connect to the server first.")
        if logged_in and self.username is None:
            raise ValueError("Log in first.")

    def handle_chat_command(self, command, arguments):
        # Preserve earlier Chat commands once their missing specification is available.
        pass

    def list_files(self):
        self._require_connection(logged_in=True)
        self.send_command("list")
        status, _ = self.receive_response(self.data_socket)
        if status == 200:
            listing = self.receive_text_line(self.data_socket)
            print(f"200 status code received. Files: {listing}")
            return listing
        print("500 status code received.")
        return None

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
        try:
            if self.control_socket is not None and self.username is not None:
                self.send_command("quit")
                status, _ = self.receive_response(self.data_socket)
                print(f"{status} status code received.")
        finally:
            self.close_connections()
            self.running = False

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
    FileTransferClient().run()


if __name__ == "__main__":
    main()
