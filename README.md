# Neural SSH Explorer

An AI-assisted SSH wrapper with a modern GUI and GPT-5-mini integration. It lets you browse remote (or local) files, preview content, run AI-driven search/navigation, and safely copy files with a double-confirmation flow. It also supports multiple SSH host profiles, tray minimization, and a quick prompt from the system tray.

## Prerequisites

- Python 3
- `pip`
- Local SSH server running (`sshd`)
- SSH keys configured (default: `~/.ssh/id_ed25519`)
- OpenAI API Key stored in `~/keys/openaikey.json`

## Installation

1.  **Dependencies**:
    Install the required Python packages:
    ```bash
    pip install paramiko openai pillow tk
    ```

2.  **Host Script**:
    The `host_functions.zsh` script is located in this directory. The client automatically sources it upon connection.
    Ensure it is executable (optional, as it is sourced):
    ```bash
    chmod +x host_functions.zsh
    ```

## Usage

1.  Run the client:
    ```bash
    python3 client.py
    ```

2.  **Interface**:
    - **Left Pane**: File preview (click a file in the middle pane).
    - **Middle Pane**: File explorer (double-click directories to navigate).
    - **Right Pane**: AI Command Center.

3.  **AI Commands**:
    Type natural language commands in the right pane, such as:
    - "Find the tax report from last year"
    - "Go to the Downloads folder"
    - "Copy the latest log file to my desktop"

4.  **Tray Mode**:
    - Closing the window hides it to the system tray (if `pystray` is installed).
    - Tray menu: Show/Hide, New Window, Quick Surf (inline prompt), Exit.
    - Quick Surf opens a tiny prompt; Enter submits and brings the main window forward with your prompt sent.

## Configuration

- **Host Profiles**: Stored in `~/.neural_ssh_hosts.json` and editable via the in-app Settings dialog.
  Example JSON:
  ```json
  {
    "default": { "host": "127.0.0.1", "user": "user", "key_path": "~/.ssh/id_ed25519" },
    "myserver": { "host": "my.server.com", "user": "alice", "key_path": "~/.ssh/id_rsa" }
  }
  ```
- **Key Selection**: Uses profile `key_path` if set, otherwise `SSH_KEY_PATH` env, otherwise first existing key in `~/.ssh` (or your SSH agent if available).
- **Defaults**: If no profiles exist, a `default` profile is used (host `127.0.0.1`, user = your OS username).

## Remote Behavior
- On connect, the client uploads `host_functions.zsh` to the remote home as `~/.host_functions.zsh`.
- Every remote command is prefixed with `source ~/.host_functions.zsh; ...` so it works without touching `~/.zshrc`.
- Works without a desktop login on the host as long as `sshd` is running and reachable.

