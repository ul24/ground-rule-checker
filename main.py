import argparse

g_debug_mode=False

def print_user_input(repo_path, commit_id):
    print("Repository Path: {}".format(repo_path))
    print("Commit ID: {}".format(commit_id))

def print_debug_info(message):
    global g_debug_mode 
    if g_debug_mode:
        print("DEBUG: {}".format(message))

def main():
    global g_debug_mode

    parser = argparse.ArgumentParser(description="Retrieve files from a specific Git commit.")
    parser.add_argument('-r', '--repo', type=str, required=True, help='Path to the Git repository')
    parser.add_argument('-c', '--commit', type=str, required=False, help='Commit ID to retrieve files from')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode.')

    args = parser.parse_args()
    repo_path = args.repo
    commit_id = args.commit
    g_debug_mode = args.debug

    print_user_input(repo_path, commit_id)

if __name__ == "__main__":
    main()
