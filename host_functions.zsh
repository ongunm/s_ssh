#!/bin/zsh

# 2. SEARCH FILES (Used by the AI engine)
function fs_list() {
    local target_dir="${1:-.}"
    # Use printf to format output cleanly for the python client
    # d=directory, f=file, etc.
    # Standard ls -la behavior but parsed
    find "$target_dir" -maxdepth 1 -mindepth 1 -printf "%y|%f|%s\n" | sort
}

function fs_search() {
    local search_term="$1"
    local search_path="${2:-.}"
    # Find files matching name, case insensitive, deeper search
    find "$search_path" -iname "*${search_term}*" -maxdepth 6 -printf "%y|%p|%s\n" 2>/dev/null | head -n 50
}

# 4. FILE SYSTEM OVERVIEW (For AI Context)
function fs_overview() {
    local root_dir="${1:-$HOME}"
    echo "--- Directory Structure (Depth 10) ---"
    # List directories depth 10, exclude hidden
    # Increased depth to 10 as requested
    find "$root_dir" -maxdepth 10 -type d -not -path '*/.*' 2>/dev/null | sed "s|$HOME|~|" | sort | head -n 500
}

# 3. GET FILE DETAILS (For the Left Pane preview)
function fs_details() {
    local file_path="$1"
    ls -lh "$file_path"
    echo "---HEAD---"
    # Show first 10 lines if it's text, otherwise say binary
    if file "$file_path" | grep -q "text"; then
        head -n 10 "$file_path"
    else
        echo "[Binary File - No Text Preview]"
    fi
}

