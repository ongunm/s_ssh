# Neural SSH Explorer

A "Split-Brain" SSH file explorer that uses GPT-5-mini to interpret natural language commands for file navigation, searching, and copying.

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

## Configuration

The client is configured by default to connect to `localhost`. You can modify `client.py` to change:
- `HOST`: Remote IP address (default: `127.0.0.1`)
- `USER`: SSH Username (set this to your username)
- `KEY_PATH`: Path to private key (default: `~/.ssh/id_ed25519`)

