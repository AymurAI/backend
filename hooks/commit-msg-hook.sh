#!/bin/sh

commit_msg_file="$1"
commit_msg=$(head -n 1 "$commit_msg_file")

# Regular expression to match Gitmoji at the start of the commit message
if ! echo "$commit_msg" | grep -qE "^(:\w+:)" || echo "$commit_msg" | grep -qE "^(:emoji:)"; then
    echo "Error: Commit message must start with a Gitmoji (e.g., :sparkles:)."
    echo "Please refer to https://gitmoji.dev/ for the list of Gitmojis."
    exit 1
fi
